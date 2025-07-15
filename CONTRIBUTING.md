# Contributing to YouTube Sync Service

First off, thank you for considering contributing to YouTube Sync Service! It's people like you that make this project better for everyone.

## Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the existing issues to avoid duplicates. When you are creating a bug report, please include as many details as possible using our [bug report template](.github/ISSUE_TEMPLATE/bug_report.md).

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. Use our [feature request template](.github/ISSUE_TEMPLATE/feature_request.md) to suggest new features.

### Your First Code Contribution

Unsure where to begin? You can start by looking through `good-first-issue` and `help-wanted` issues.

## Development Setup

### Prerequisites

- Python 3.11 or higher
- Docker (optional, for containerized development)
- Git

### Setting Up Development Environment

1. **Fork and Clone**
   ```bash
   git clone https://github.com/YOUR_USERNAME/ytsync.git
   cd ytsync
   ```

2. **Create Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   pip install black isort pylint bandit  # Development tools
   ```

4. **Copy Example Configuration**
   ```bash
   cp config.yaml.example config.yaml
   # Edit config.yaml with your settings
   ```

## Code Style

We use several tools to maintain code quality:

- **Black** for code formatting
- **isort** for import sorting
- **Pylint** for code linting
- **Bandit** for security checks

### Running Code Quality Checks

```bash
# Format code
black main.py
isort main.py

# Check formatting
black --check main.py
isort --check-only main.py

# Lint code
pylint main.py

# Security scan
bandit -r main.py
```

## Pull Request Process

1. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/issue-description
   ```

2. **Make Your Changes**
   - Write clear, concise commit messages
   - Follow the existing code style
   - Add tests if applicable
   - Update documentation as needed

3. **Test Your Changes**
   ```bash
   # Run the service locally
   python main.py

   # Test with Docker
   docker-compose up --build
   ```

4. **Run Quality Checks**
   ```bash
   black --check main.py
   isort --check-only main.py
   pylint main.py
   ```

5. **Commit and Push**
   ```bash
   git add .
   git commit -m "type: brief description of changes"
   git push origin your-branch-name
   ```

6. **Create Pull Request**
   - Use our [PR template](.github/pull_request_template.md)
   - Link related issues
   - Provide clear description of changes

## Commit Message Convention

We follow a simple commit message convention:

```
type: brief description

Longer description if needed

- Bullet points for details
- Use imperative mood ("add" not "added")
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance tasks

## Testing

### Manual Testing

1. **Basic functionality**
   ```bash
   # Test configuration loading
   python main.py --help

   # Test with sample config
   python main.py
   ```

2. **Docker testing**
   ```bash
   # Build and test container
   docker-compose up --build
   ```

3. **Different configurations**
   - Test with various YouTube sources
   - Test error handling
   - Test configuration reloading

### Adding Tests

While we don't have automated tests yet, you can help by:
- Adding unit tests for new functions
- Creating integration tests
- Documenting test scenarios

## Documentation

### Code Documentation

- Add docstrings to all functions and classes
- Use clear, descriptive variable names
- Comment complex logic

### User Documentation

- Update README.md for new features
- Add configuration examples
- Update troubleshooting guide

## Release Process

Releases are managed by maintainers, but contributors can help by:
- Updating CHANGELOG.md
- Testing release candidates
- Reporting issues with new versions

## Getting Help

- **Discord/Telegram**: [Community links if available]
- **GitHub Issues**: For bugs and feature requests
- **GitHub Discussions**: For questions and general discussion

## Recognition

Contributors will be recognized in:
- CHANGELOG.md for their contributions
- GitHub contributors list
- Release notes for significant contributions

Thank you for contributing! 🎉
