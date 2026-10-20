"""Batched S3Gen for the chatterbox-vllm worker: speech tokens in, one wav per take out.

The port batches T3 but runs S3Gen (flow encoder, 10-step CFM, HiFiGAN) one take at
a time. This runs the flow for a sub-batch of takes at once: each take's tokens go
after the shared reference prompt, right-padded to the longest, with masks marking
the padding. Every layer that mixes time steps is causal or masked, except the
encoder's 3-token lookahead conv, which would read the padding's nonzero
embeddings; `_zero_padding_before_lookahead` zeroes them, as the unbatched pad does.

The flow can run under CUDA autocast (`flow_dtype`): fp32, its GEMMs and attention
are compute-bound, so batching alone saves ~10%; under fp16 the batched flow takes
~4.5 s for 48 takes against ~16 s per take in fp32.

HiFiGAN still runs per take, in fp32: its convs look ahead and it draws fresh noise per call,
so padding would change each take's tail, and it costs little next to the CFM.

The planning helpers are pure so CI can test them without torch; the torch import
is deferred to the GPU path. It imports nothing from `src`, like the worker.
"""

from contextlib import contextmanager, nullcontext

MEL_FRAMES_PER_TOKEN = 2


def plan_sub_batches(lengths: list[int], prompt_len: int, max_padded_tokens: int) -> list[list[int]]:
    """Group take indices longest-first so each group's padded size fits the budget.

    A group of n takes costs n * (prompt_len + its longest take); a take too long
    for the budget alone still gets a group of its own.
    """
    order = sorted(range(len(lengths)), key=lambda i: (-lengths[i], i))
    groups: list[list[int]] = []
    for index in order:
        if groups and (len(groups[-1]) + 1) * (prompt_len + lengths[groups[-1][0]]) <= max_padded_tokens:
            groups[-1].append(index)
        else:
            groups.append([index])
    return groups


def restore_order(groups: list[list[int]], grouped_outputs: list[list]) -> list:
    """Undo plan_sub_batches: outputs back in the order the takes came in."""
    total = sum(len(group) for group in groups)
    ordered: list = [None] * total
    for group, outputs in zip(groups, grouped_outputs):
        if len(group) != len(outputs):
            raise ValueError(f"sub-batch of {len(group)} takes returned {len(outputs)} outputs")
        for index, output in zip(group, outputs):
            ordered[index] = output
    return ordered


def take_mel_spans(lengths: list[int], prompt_mel_len: int) -> list[tuple[int, int]]:
    """Each take's own mel frames in the padded batch: after the prompt, before its padding."""
    return [(prompt_mel_len, prompt_mel_len + MEL_FRAMES_PER_TOKEN * length) for length in lengths]


class BatchedS3Gen:
    def __init__(self, s3gen, max_padded_tokens: int, flow_dtype: str | None = None):
        self.s3gen, self.max_padded_tokens, self.flow_dtype = s3gen, max_padded_tokens, flow_dtype

    def wavs(self, token_seqs: list, ref: dict, n_timesteps: int) -> list:
        """One wav tensor (1, samples) per token sequence, in input order."""
        lengths = [int(tokens.numel()) for tokens in token_seqs]
        groups = plan_sub_batches(lengths, int(ref["prompt_token"].shape[1]), self.max_padded_tokens)
        mels = [self.mels([token_seqs[i] for i in group], ref, n_timesteps) for group in groups]
        return [self.vocode(mel) for mel in restore_order(groups, mels)]

    def mels(self, token_seqs: list, ref: dict, n_timesteps: int) -> list:
        """The flow for one padded sub-batch: one (80, frames) mel per take."""
        import torch

        autocast = nullcontext() if self.flow_dtype is None else torch.autocast("cuda", dtype=getattr(torch, self.flow_dtype))
        with torch.inference_mode(), autocast:
            return _flow_mels(self.s3gen.flow, token_seqs, ref, n_timesteps)

    def vocode(self, mel):
        """HiFiGAN for one take's mel, with the port's fade-in over the reference spillover."""
        with _inference_mode():
            wav, _ = self.s3gen.hift_inference(mel.unsqueeze(0), None)
            wav[:, :len(self.s3gen.trim_fade)] *= self.s3gen.trim_fade
            return wav.cpu()


def _inference_mode():
    import torch

    return torch.inference_mode()


def _flow_mels(flow, token_seqs: list, ref: dict, n_timesteps: int) -> list:
    """CausalMaskedDiffWithXvec.inference (finalize=True) for a padded batch of takes."""
    import torch
    import torch.nn.functional as F
    from chatterbox_vllm.models.s3gen.utils.mask import make_pad_mask

    prompt_token, prompt_feat, embedding = ref["prompt_token"], ref["prompt_feat"], ref["embedding"]
    if flow.fp16:
        prompt_feat, embedding = prompt_feat.half(), embedding.half()
    batch, device = len(token_seqs), prompt_token.device
    speech = torch.nn.utils.rnn.pad_sequence([t.reshape(-1).to(device) for t in token_seqs], batch_first=True)
    lengths = [int(t.numel()) for t in token_seqs]
    token_lens = torch.tensor(lengths, device=device) + prompt_token.shape[1]
    tokens = torch.cat([prompt_token.expand(batch, -1), speech], dim=1)

    spks = flow.spk_embed_affine_layer(F.normalize(embedding, dim=1)).expand(batch, -1)
    token_mask = (~make_pad_mask(token_lens, tokens.shape[1])).unsqueeze(-1).to(spks)
    embedded = flow.input_embedding(torch.clamp(tokens, min=0, max=flow.input_embedding.num_embeddings - 1)) * token_mask
    with _zero_padding_before_lookahead(flow.encoder, token_mask):
        h, _ = flow.encoder(embedded, token_lens)
    mu = flow.encoder_proj(h).transpose(1, 2).contiguous()

    frames, prompt_mel_len = mu.shape[2], prompt_feat.shape[1]
    cond = torch.zeros(batch, flow.output_size, frames, device=device, dtype=mu.dtype)
    cond[:, :, :prompt_mel_len] = prompt_feat.transpose(1, 2)
    mel_mask = (~make_pad_mask(token_lens * MEL_FRAMES_PER_TOKEN, frames)).unsqueeze(1).to(mu)
    feat = _solve_euler(flow.decoder, mu, mel_mask, spks, cond, n_timesteps)
    return [feat[row, :, start:end] for row, (start, end) in enumerate(take_mel_spans(lengths, prompt_mel_len))]


@contextmanager
def _zero_padding_before_lookahead(encoder, token_mask):
    hook = encoder.pre_lookahead_layer.register_forward_pre_hook(lambda _module, args: (args[0] * token_mask,))
    try:
        yield
    finally:
        hook.remove()


def _solve_euler(cfm, mu, mask, spks, cond, n_timesteps: int):
    """CausalConditionalCFM.forward + solve_euler, with the CFG pair stacked per take, not fixed at 2 rows."""
    import torch

    x = cfm.rand_noise[:, :, :mu.shape[2]].to(mu.device, mu.dtype).expand_as(mu)
    t_span = torch.linspace(0, 1, n_timesteps + 1, device=mu.device, dtype=mu.dtype)
    if cfm.t_scheduler == "cosine":
        t_span = 1 - torch.cos(t_span * 0.5 * torch.pi)
    t, dt = t_span[0], t_span[1] - t_span[0]
    mask_in, mu_in = torch.cat([mask, mask]), torch.cat([mu, torch.zeros_like(mu)])
    spks_in, cond_in = torch.cat([spks, torch.zeros_like(spks)]), torch.cat([cond, torch.zeros_like(cond)])
    rate = cfm.inference_cfg_rate
    for step in range(1, n_timesteps + 1):
        t_in = t.expand(2 * mu.shape[0])
        dphi_dt, cfg_dphi_dt = cfm.forward_estimator(torch.cat([x, x]), mask_in, mu_in, t_in, spks_in, cond_in).chunk(2)
        x = x + dt * ((1.0 + rate) * dphi_dt - rate * cfg_dphi_dt)
        t = t + dt
        if step < n_timesteps:
            dt = t_span[step + 1] - t
    return x.float()
