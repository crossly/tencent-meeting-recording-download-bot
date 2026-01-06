# Changelog

All notable changes to this project will be documented in this file.

## [1.1.0] - 2025-01-06

### Added
- **Multi-recording support**: URLs with multiple recordings are now fully supported
- **Direct download mode**: Support for recordings that use `signurl` direct download (in addition to multi-stream HLS)
- **New commands**:
  - `/list <URL>` - List all available recordings without downloading
  - `/download_all <URL>` - Download all recordings from a URL
- **CLI improvements**:
  - `python main.py --all <URL>` to download all recordings
  - `python main.py <URL>` to download first recording (unchanged)
- **Page data fallback**: When API returns empty results, recordings are extracted from page HTML as fallback

### Fixed
- **Critical bug**: Some recording URLs (using direct download mode) would fail with "No streams available"
- Recording info extraction now handles both API response and embedded page data

### Changed
- Refactored download logic into `download_all()` method for better code organization
- `start_download()` now uses `download_all(max_count=1)` internally for consistency

## [1.0.0] - 2025-01-05

### Added
- Initial release
- Dual-mode operation (Bot mode and Client mode)
- Automatic stream selection (Screen Share preferred)
- FFmpeg-based video splitting for Bot mode (>50MB files)
- Cookie management via Telegram commands
- HLS stream download with AES decryption support
