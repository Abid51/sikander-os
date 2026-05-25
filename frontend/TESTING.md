# Frontend Testing Guide

## 🎯 Overview

This project uses **Vitest** for unit testing and **Testing Library** for React component testing. All tests follow best practices for accessibility and behavior-driven testing.

## 📦 Installation

```bash
cd frontend
npm install
```

## 🚀 Running Tests

### Run All Tests
```bash
npm test
```

### Watch Mode (Auto-rerun on file changes)
```bash
npm test -- --watch
```

### Interactive Dashboard
```bash
npm run test:ui
```

### Generate Coverage Report
```bash
npm run test:coverage
```

## 📊 Coverage Goals

| Component | Status | Target |
|-----------|--------|--------|
| ChatMessage | ✅ Complete | 100% |
| CommandPalette | ⏳ Pending | 90%+ |
| DaemonCommandDrawer | ⏳ Pending | 90%+ |
| SettingsModal | ⏳ Pending | 85%+ |
| VoiceOrb | ⏳ Pending | 80%+ |
| API Utils | ⏳ Pending | 95%+ |

**Current Overall Coverage Target: 85%+**

## 📝 Writing Tests

### Basic Component Test

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import MyComponent from '../MyComponent';

describe('MyComponent', () => {
  it('renders correctly', () => {
    render(<MyComponent />);
    expect(screen.getByText('Expected Text')).toBeInTheDocument();
  });
});
```

### Testing User Interactions

```typescript
import userEvent from '@testing-library/user-event';

it('handles click events', async () => {
  const mockFn = vi.fn();
  const user = userEvent.setup();
  
  render(<MyComponent onClick={mockFn} />);
  
  await user.click(screen.getByRole('button'));
  expect(mockFn).toHaveBeenCalled();
});
```

## ✅ Best Practices

### DO:
- ✅ Test user-facing behavior, not implementation
- ✅ Use semantic queries: `getByRole`, `getByLabelText`
- ✅ Test accessibility features (ARIA labels)
- ✅ Use `userEvent` instead of `fireEvent`
- ✅ Mock external APIs and dependencies
- ✅ Keep tests focused and isolated

### DON'T:
- ❌ Test implementation details or internal state
- ❌ Use `querySelector` directly
- ❌ Skip accessibility tests

## 🎯 Implemented Tests

### ChatMessage ✅ (16 comprehensive tests)
- User message rendering
- Assistant message with markdown
- GFM features (tables, code blocks)
- Link security
- Feedback system
- Accessibility compliance

## 📖 Resources

- [Vitest Documentation](https://vitest.dev)
- [Testing Library](https://testing-library.com)
- [Best Practices](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)
