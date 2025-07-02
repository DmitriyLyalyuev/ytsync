# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Web UI for configuration and monitoring
- REST API for integration
- Support for additional video platforms
- Notification system (Telegram, Discord, Email)
- Plugin system for extensibility

## [1.1.0] - 2025-07-02

### Changed
- **Dependencies Updates**
  - Updated yt-dlp from 2025.06.09 to 2025.6.25 (security fixes and improvements)
  - Updated PyYAML from 6.0.1 to 6.0.2 (security update)
  - Updated requests from 2.31.0 to 2.32.4 (security update)

### Added
- **Authentication Improvements**
  - Enhanced cookies support for better authentication handling
  - Simplified cookie configuration management
  - Improved metadata fetching with proper authentication

### Fixed
- **Code Quality & CI/CD**
  - Fixed formatting issues throughout codebase
  - Improved logging placement and timing
  - Fixed Pylint configuration and warnings
  - Enhanced Trivy security scanning configuration
  - Fixed workflow issues in GitHub Actions

### Infrastructure
- **Automated Dependency Management**
  - Added Dependabot configuration for automatic security updates
  - Automated dependency vulnerability monitoring
  - Improved CI/CD pipeline reliability

## [1.0.0] - 2024-12-26

### Added
- **Core Features**
  - Automatic YouTube channel and playlist synchronization
  - SQLite database for tracking downloaded videos
  - YAML configuration with per-source settings
  - Intelligent filtering by date, file size, and duration
  - Built-in scheduler for automated synchronization
  - Comprehensive logging system

- **Docker Support**
  - Multi-platform Docker images (amd64, arm64)
  - Docker Compose configuration
  - Configurable UID/GID for proper file permissions
  - Health checks and resource limits

- **Plex Integration**
  - Plex TV Shows compatible naming format
  - Season-based organization by year
  - Automatic directory structure creation
  - MP4 format prioritization with FFmpeg

- **Quality Control**
  - Flexible quality settings with yt-dlp format strings
  - File size and duration limitations
  - Configurable video processing options
  - Error handling and retry logic

- **CI/CD Pipeline**
  - GitHub Actions workflow for automated builds
  - Multi-platform container builds
  - Security scanning with Bandit and Trivy
  - Code quality checks with Black, isort, and Pylint
  - Automated publishing to GitHub Container Registry

- **Documentation**
  - Comprehensive README with usage examples
  - MIT license
  - Issue and PR templates
  - Contributing guidelines
  - FAQ and troubleshooting guide
  - Use case scenarios

### Technical Details
- **Languages**: Python 3.11+
- **Dependencies**: yt-dlp, PyYAML, schedule, SQLite3
- **Container Registry**: GitHub Container Registry (ghcr.io)
- **Supported Platforms**: Linux (amd64, arm64), macOS, Windows
- **File Formats**: MP4 (preferred), WebM, MKV
- **Quality Options**: 1080p, 720p, 480p with customizable settings

### Configuration Features
- Individual output directories per source
- Customizable sync intervals and schedules
- Period-based filtering (last N days)
- Maximum videos per source limiting
- Automatic configuration reloading
- Environment variable support

### Security & Reliability
- Non-privileged container execution
- Input validation and sanitization
- Database transaction safety
- Graceful error handling
- Resource usage monitoring
- Automated vulnerability scanning

---

## Version History

- **v1.0.0**: Initial stable release with full feature set
- **v0.x.x**: Development and testing versions (not released)

## Migration Guide

### From Development Version
If you were using a development version, please:
1. Backup your `config.yaml` and `db/` directory
2. Update to the latest Docker image or Python package
3. Review configuration for any new options
4. Test with a small subset of sources first

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to contribute to this project.

## Support

- **Issues**: [GitHub Issues](https://github.com/DmitriyLyalyuev/ytsync/issues)
- **Discussions**: [GitHub Discussions](https://github.com/DmitriyLyalyuev/ytsync/discussions)
- **Documentation**: [README.md](README.md)