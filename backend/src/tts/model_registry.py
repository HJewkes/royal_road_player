"""Fine-tuned TTS model registry system."""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, List
import yaml

logger = logging.getLogger(__name__)


@dataclass
class FineTunedModel:
    """Fine-tuned TTS model definition."""
    name: str
    repo: str  # HuggingFace repository ID
    sub_path: str  # Subdirectory path within repo (empty string for root)
    language: str  # Language code (e.g., 'eng', 'spa')
    voice_ref: Optional[str] = None  # Path to reference voice WAV file
    description: Optional[str] = None  # Human-readable description
    rating: Optional[Dict[str, int]] = None  # Quality ratings (GPU VRAM, CPU, RAM, Realism)


# Default fine-tuned models (from ebook2audiobook)
DEFAULT_MODELS: Dict[str, FineTunedModel] = {
    "default": FineTunedModel(
        name="default",
        repo="coqui/XTTS-v2",
        sub_path="",
        language="multi",
        description="Default XTTS v2 multilingual model",
    ),
    "david_attenborough": FineTunedModel(
        name="david_attenborough",
        repo="drewThomasson/fineTunedTTSModels",
        sub_path="xtts-v2/eng/DavidAttenborough/",
        language="eng",
        description="David Attenborough voice (elder, male)",
        rating={"GPU VRAM": 4, "CPU": 3, "RAM": 8, "Realism": 5},
    ),
    "morgan_freeman": FineTunedModel(
        name="morgan_freeman",
        repo="drewThomasson/fineTunedTTSModels",
        sub_path="xtts-v2/eng/MorganFreeman/",
        language="eng",
        description="Morgan Freeman voice (adult, male)",
        rating={"GPU VRAM": 4, "CPU": 3, "RAM": 8, "Realism": 5},
    ),
    "scarlett_johansson": FineTunedModel(
        name="scarlett_johansson",
        repo="drewThomasson/fineTunedTTSModels",
        sub_path="xtts-v2/eng/ScarlettJohansson/",
        language="eng",
        description="Scarlett Johansson voice (adult, female)",
        rating={"GPU VRAM": 4, "CPU": 3, "RAM": 8, "Realism": 5},
    ),
    "neil_gaiman": FineTunedModel(
        name="neil_gaiman",
        repo="drewThomasson/fineTunedTTSModels",
        sub_path="xtts-v2/eng/NeilGaiman/",
        language="eng",
        description="Neil Gaiman voice (adult, male)",
        rating={"GPU VRAM": 4, "CPU": 3, "RAM": 8, "Realism": 5},
    ),
    "ray_porter": FineTunedModel(
        name="ray_porter",
        repo="drewThomasson/fineTunedTTSModels",
        sub_path="xtts-v2/eng/RayPorter/",
        language="eng",
        description="Ray Porter voice (adult, male)",
        rating={"GPU VRAM": 4, "CPU": 3, "RAM": 8, "Realism": 5},
    ),
}


class ModelRegistry:
    """Registry for fine-tuned TTS models."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize model registry.
        
        Args:
            config_path: Optional path to custom model registry YAML file
        """
        self.models: Dict[str, FineTunedModel] = {}
        self.config_path = config_path
        self._load_registry()
    
    def _load_registry(self) -> None:
        """Load model registry from config file or use defaults."""
        # Start with default models
        self.models = DEFAULT_MODELS.copy()
        
        # Load custom models from config file if provided
        if self.config_path and self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    if self.config_path.suffix in ['.yaml', '.yml']:
                        try:
                            data = yaml.safe_load(f)
                        except ImportError:
                            logger.warning("YAML not available, skipping custom models")
                            return
                    else:
                        import json
                        data = json.load(f)
                
                # Merge custom models
                for name, model_data in data.items():
                    if isinstance(model_data, dict):
                        model = FineTunedModel(
                            name=name,
                            repo=model_data.get('repo', ''),
                            sub_path=model_data.get('sub_path', ''),
                            language=model_data.get('language', 'eng'),
                            voice_ref=model_data.get('voice_ref'),
                            description=model_data.get('description'),
                            rating=model_data.get('rating'),
                        )
                        self.models[name] = model
                        logger.info(f"Loaded custom model: {name}")
                
            except Exception as e:
                logger.warning(f"Failed to load custom model registry: {e}")
    
    def get_model(self, name: str) -> Optional[FineTunedModel]:
        """
        Get model by name.
        
        Args:
            name: Model name
            
        Returns:
            FineTunedModel if found, None otherwise
        """
        return self.models.get(name)
    
    def list_models(self, language: Optional[str] = None) -> List[FineTunedModel]:
        """
        List all available models, optionally filtered by language.
        
        Args:
            language: Optional language code to filter by
            
        Returns:
            List of FineTunedModel objects
        """
        models = list(self.models.values())
        if language:
            models = [m for m in models if m.language == language or m.language == 'multi']
        return sorted(models, key=lambda m: m.name)
    
    def get_model_path(self, model: FineTunedModel) -> str:
        """
        Get HuggingFace model path for a model.
        
        Args:
            model: FineTunedModel instance
            
        Returns:
            Model path string (e.g., "repo/sub_path" or "repo")
        """
        if model.sub_path:
            return f"{model.repo}/{model.sub_path.rstrip('/')}"
        return model.repo
    
    def save_registry(self, output_path: Optional[Path] = None) -> None:
        """
        Save current registry to file.
        
        Args:
            output_path: Optional output path (defaults to config_path)
        """
        if output_path is None:
            output_path = self.config_path
        
        if output_path is None:
            logger.warning("No output path specified for saving registry")
            return
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to serializable format
        data = {}
        for name, model in self.models.items():
            # Skip default model
            if name == "default":
                continue
            
            model_dict = {
                'repo': model.repo,
                'sub_path': model.sub_path,
                'language': model.language,
            }
            if model.voice_ref:
                model_dict['voice_ref'] = model.voice_ref
            if model.description:
                model_dict['description'] = model.description
            if model.rating:
                model_dict['rating'] = model.rating
            
            data[name] = model_dict
        
        # Save to file
        with open(output_path, 'w', encoding='utf-8') as f:
            if output_path.suffix in ['.yaml', '.yml']:
                try:
                    yaml.dump(data, f, default_flow_style=False, sort_keys=False)
                except ImportError:
                    import json
                    json.dump(data, f, indent=2)
            else:
                import json
                json.dump(data, f, indent=2)
        
        logger.info(f"Saved model registry to {output_path}")


def get_model_registry(config_path: Optional[Path] = None) -> ModelRegistry:
    """
    Get model registry instance.
    
    Args:
        config_path: Optional path to custom model registry config file
        
    Returns:
        ModelRegistry instance
    """
    if config_path is None:
        # Try default location
        project_root = Path(__file__).parent.parent.parent.parent
        config_path = project_root / "data" / "models" / "fine_tuned_models.yaml"
    
    return ModelRegistry(config_path)
