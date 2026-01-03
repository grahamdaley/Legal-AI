---
trigger: always_on
---

# Technical Requirements for TypeScript Code Generation (LLM Prompt)

This document outlines the technical requirements for generating high-quality TypeScript code using an LLM (e.g., Claude). Adhering to these guidelines will help ensure the generated code is robust, maintainable, performant, and follows best practices.

## 1. Core Principles

- **Correctness:** The generated code must be functionally correct and meet all specified requirements.
- **Readability & Maintainability:** Code should be clean, well-structured, and easy to understand and modify by human developers.
- **Performance:** Code should be efficient and avoid unnecessary overhead, especially for common operations.
- **Security:** Code must be free from common vulnerabilities (e.g., injection flaws, improper data handling).
- **Scalability:** Consider future growth and ensure the design can accommodate increased load or complexity.
- **Testability:** Code should be designed with testing in mind, making it easy to write unit, integration, and end-to-end tests.
- **TypeScript Best Practices:** Adhere to modern TypeScript conventions, type safety, and language features.

## 2. General Code Generation Requirements

### Type Safety and Precision

- **Strict Type Enforcement:** Utilize TypeScript's strict mode features (`strict: true` in `tsconfig.json`) where appropriate. Avoid `any` type unless absolutely necessary and with clear justification.
- **Specific Types:** Use the most specific types possible (e.g., `string`, `number`, `boolean`, `Array<T>`, `interface`, `type alias`) rather than `object` or `unknown` when a more precise type is known.
- **Literal Types:** Employ literal types for fixed values (e.g., `'success'`, `'error'`) to enhance type safety and enable better compile-time checks.
- **Discriminated Unions:** Use discriminated unions for handling different shapes of data based on a common discriminant property.
- **Generics:** Utilize generics to create reusable and type-safe components, functions, and classes that can work with various data types.
- **Null and Undefined Handling:** Explicitly handle `null` and `undefined` using optional chaining (`?.`), nullish coalescing (`??`), and type guards.

### Type Definitions

- Prefer types over interfaces for consistency
- Use explicit return types for functions
- Leverage discriminated unions for complex states
- Prefer "types" to "interfaces" where relevant
- Avoid exporting functions that are only used internally

#### Examples

```typescript
// ✅ Good: Discriminated union with explicit types
type RequestState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "error"; error: Error };

// ✅ Good: Const assertion
const ActionTypes = {
  CREATE: "create",
  UPDATE: "update",
  DELETE: "delete",
} as const;

// ❌ Bad: Avoid enums
enum ActionTypes {
  CREATE,
  UPDATE,
  DELETE,
}
```

### Code Structure and Organization

- **Modular Design:** Break down complex logic into smaller, focused modules (files) with clear responsibilities.
- **Single Responsibility Principle (SRP):** Each function, class, or module should have one clearly defined purpose.
- **Clear Export/Import Strategy:** Use named exports (`export const ...`) and default exports (`export default ...`) appropriately to define the public API of modules.
- **Directory Structure:** Organize files logically into directories (e.g., `src/components`, `src/services`, `src/utils`).

### Naming Conventions

- **CamelCase for Variables and Functions:** `myVariable`, `myFunction`.
- **PascalCase for Classes, Interfaces, and Type Aliases:** `MyClass`, `IMyInterface`, `MyType`.
- **ALL_CAPS_SNAKE_CASE for Constants:** `MAX_RETRIES`.
- **Descriptive Names:** Names should clearly convey the purpose and content of the variable, function, class, etc. Avoid abbreviations unless universally understood.

### Comments and Documentation

- **JSDoc:** Use JSDoc for documenting functions, classes, interfaces, and public API elements. Include `@param`, `@returns`, `@throws`, `@example` tags as appropriate.
- **Inline Comments:** Use inline comments sparingly for complex or non-obvious logic.
- **Explanation of Design Choices:** Comment on significant design decisions or trade-offs made.

### Error Handling

- **Robust Error Handling:** Implement comprehensive error handling using `try...catch` blocks for synchronous code and promises/async-await for asynchronous code.
- **Custom Error Classes:** Define custom error classes for specific application errors to provide more context.
- **Meaningful Error Messages:** Error messages should be clear, concise, and provide sufficient information for debugging or user feedback.
- **Logging:** Integrate with a logging mechanism (e.g., `console.error`, a dedicated logging library) to record errors.

### Asynchronous Operations

- **Async/Await:** Prefer `async/await` for handling asynchronous operations, as it improves readability and error handling compared to `.then().catch()`.
- **Promise-Based APIs:** If using Promise-based APIs, ensure proper chaining and error propagation.
- **Concurrency Control:** Consider mechanisms for limiting concurrent operations if performance or resource constraints are a concern.

### 2.7. Immutability

- **Favor Immutability:** Where possible, prefer immutable data structures to simplify reasoning about state changes and prevent unintended side effects.
- **`const` and `readonly`:** Use `const` for variables that are not reassigned and `readonly` for properties that should not be modified after initialization.

### 2.8. Performance Considerations

- **Avoid Unnecessary Computations:** Cache results of expensive computations if they are frequently accessed and their inputs don't change often.
- **Efficient Data Structures:** Choose appropriate data structures for the task (e.g., `Map` for key-value lookups, `Set` for unique items).
- **Minimize Loop Iterations:** Optimize loops and avoid nested loops where a more efficient algorithm exists.

### 2.9. Security Considerations

- **Input Validation:** Always validate and sanitize all external inputs to prevent injection attacks (XSS, SQL injection if applicable, etc.).
- **Sensitive Data Handling:** Never log or expose sensitive information (e.g., passwords, API keys) without proper obfuscation or encryption.
- **Authentication and Authorization:** If applicable, ensure robust authentication and authorization mechanisms are in place.

## 3. Specific TypeScript Feature Requirements

- **Interfaces vs. Type Aliases:**
  - Use `interface` for defining object shapes (especially when extending or implementing).
  - Use `type` for defining unions, intersections, primitive aliases, or complex type manipulations.
- **Enums:** Prefer `const enum` for better performance and smaller bundle sizes if the enum values are known at compile time and don't require runtime reflection. Otherwise, use regular `enum` or union types.
- **Decorators:** If used, ensure they follow common patterns and are well-documented.
- **Utility Types:** Leverage built-in TypeScript utility types (`Partial<T>`, `Pick<T, K>`, `Omit<T, K>`, `Exclude<T, U>`, `NonNullable<T>`, `Record<K, T>`, etc.) to create flexible and type-safe code.
- **Type Guards:** Implement custom type guards for refining types within conditional blocks.

## 4. Testing Requirements (Implicit for LLM, Explicit for Human Review)

While the LLM won't _write_ tests unless specifically prompted, the generated code should implicitly meet these requirements for testability:

- **Pure Functions:** Favor pure functions (functions that, given the same inputs, always return the same output and have no side effects) for easier testing.
- **Dependency Injection (DI):** Design components to receive their dependencies rather than creating them internally, enabling easier mocking in tests.
- **Small, Focused Units:** Functions and classes should be small and focused, making it easier to test them in isolation.