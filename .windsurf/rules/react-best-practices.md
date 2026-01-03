---
trigger: always_on
---

# React and State Management

## 1. Naming and Structure

### File Organization

- `components/` - React components using PascalCase (UserProfile.tsx)
- `utils/` - Utility functions using camelCase (formatDate.ts)
- `hooks/` - Custom React hooks prefixed with 'use' (useAuth.ts)
- `types/` - TypeScript type definitions (UserTypes.ts)

### Naming Patterns

- Components: PascalCase (e.g., `DataTable.tsx`)
- Utilities: camelCase (e.g., `stringUtils.ts`)
- Hooks: camelCase with 'use' prefix (e.g., `useQueryState.ts`)
- Constants: UPPER_SNAKE_CASE (e.g., `MAX_RETRY_COUNT`)

### File size, module structure, exports, functional purity

- Try to keep a file/module as a cohesive unit, generally trying to keep number of lines under 250
- Avoid exporting functions that are only used internally
- Avoid overly long and complex functions, break them down to smaller, focused functions following a functional style
- Try to avoid mutations and global state wherever possible

### Component Structure

```typescript
// ✅ Good: Functional component with proper types
type Props = {
  items: Item[];
  onSelect: (item: Item) => void;
};

const ItemList: React.FC<Props> = ({ items, onSelect }) => {
  const [selected, setSelected] = useState<Item | null>(null);

  useEffect(() => {
    return () => {
      // Cleanup
    };
  }, []);

  return <div>{/* JSX */}</div>;
};
```

## 2. State Management Rules

- Use React Query for server state
- Context for global UI state
- Local state for component-specific data

## 3. Error Handling and Security

### Error Boundaries

```typescript
class ErrorBoundary extends React.Component<Props, State> {
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return <ErrorDisplay error={this.state.error} />;
    }
    return this.props.children;
  }
}
```

## 3. Security Checklist

- ✅ Sanitize all user inputs
- ✅ Implement proper CSP headers
- ✅ Use HTTPS for all API calls
- ✅ Follow CORS best practices
- ✅ Store secrets only in env vars or secret managers; **never hardcoded**.
- ✅ Ensure error responses (esp. 4xx/5xx) do not leak stack traces or sensitive info.