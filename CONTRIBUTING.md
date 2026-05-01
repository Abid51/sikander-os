# Contributing to Sikander OS

Thank you for your interest in contributing! Here's how to get started.

## Setup

1. **Fork the repository**
2. **Clone your fork:** `git clone https://github.com/YOUR_USERNAME/sikander-os.git`
3. **Create a branch:** `git checkout -b fix/issue-name`
4. **Follow [DEVELOPMENT.md](DEVELOPMENT.md) for setup**

## Code Standards

### Python

- **Style:** PEP 8 via Black
- **Linting:** Pylint (7.0+)
- **Type hints:** Encouraged for public APIs
- **Tests:** Required for new features

```bash
# Format
black backend/app

# Lint
pylint backend/app --fail-under=7.0
```

### JavaScript/TypeScript

- **Style:** Prettier
- **Linting:** ESLint

```bash
# Format
cd frontend && npm run format

# Lint
npm run lint
```

## Commit Guidelines

Use conventional commits:

```
fix: Resolve hotkey threading issue
feat: Add new daemon system
docs: Update README
test: Add security tests
ci: Setup GitHub Actions
chore: Update dependencies
```

## Pull Request Process

1. **Ensure tests pass:** `npm run test:backend`
2. **Update documentation** if needed
3. **Reference issues:** "Fixes #123"
4. **Describe changes** clearly
5. **Wait for review** and CI/CD ✅

## Issues & Feature Requests

- **Bug Report:** Use "🐛 Bug" template
- **Feature Request:** Use "✨ Feature" template
- **Question:** Use "❓ Question" template

## Reporting Security Issues

⚠️ **Do NOT open public issues for security vulnerabilities**

Email: security@sikander-os.dev (if available)

---

**Questions?** Open a discussion or contact maintainers.

Thank you! 🚀
