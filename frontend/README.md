# Frontend

TypeScript/React frontend for the Audiobook System.

## Structure

- `src/components/` - React components with CSS modules
- `src/store/` - Zustand state management stores
- `src/styles/` - Global styles and CSS variables
- `src/types/` - TypeScript type definitions
- `src/App.tsx` - Main application component
- `src/main.tsx` - Application entry point

## Development

```bash
# Install dependencies
npm install

# Run development server (with hot reload)
npm run dev

# Build for production
npm run build

# Type checking
npm run type-check

# Linting
npm run lint
```

## Build Output

The build output goes to `frontend/dist/` where it's served by the FastAPI backend.

## Technology Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **Zustand** - State management
- **Lucide React** - Icon library
- **CSS Modules** - Scoped styling

