# ANNA

**ANNA — Interactive Video Activities for Augmentative and Alternative Communication**

ANNA is an open-source desktop application for creating and using interactive video activities in the field of augmentative and alternative communication (AAC).

The software allows professionals to prepare video-based activities in which playback can be interrupted at predefined points to present interactive hotspots and visual supports. ANNA provides separate Professional and User modes and includes optional research-session recording and data export.

## Main features

- Creation and editing of video-based AAC activities.
- Definition of timed pause events within videos.
- Interactive hotspots associated with video pauses.
- Visual supports that can be configured independently from hotspots.
- Navigation between videos and interactive elements.
- Separate Professional and User modes.
- Optional research-session recording.
- Structured storage of interaction events and session summaries.
- Export of research data to CSV.
- Local management of participants for research sessions.
- Demonstration project included with the software.
- English and Spanish interface.

## Version

Current release: **ANNA 1.0.0**

ANNA is developed in Python using PySide6/Qt.

## Requirements

### Windows executable

A packaged Windows version is provided with the ANNA 1.0.0 release.

The packaged application includes the Python runtime and the libraries required to run ANNA. Users of the packaged version do not need to install Python separately.

Download `ANNA-1.0.0-Windows.zip` from the GitHub Releases section, extract the complete ZIP file, and run `ANNA.exe` from the extracted `ANNA-1.0.0-Windows` folder.

The complete folder must be retained because the executable depends on the libraries and resources distributed with it.

### Running from source

Python 3.12 is recommended.

Install the required dependencies:

```bash
python -m pip install -r requirements.txt
```

Then start ANNA from the project source.

## Demonstration project

ANNA includes a demonstration project that can be used to explore the main workflow without first creating a project from scratch.

The demonstration materials are located in the `demo_project` directory. Additional information about these materials and their licensing is provided in the documentation contained in that directory.

### Demonstration media

The videos included in the demonstration project were created by the ANNA authors and are distributed under the **Creative Commons Attribution 4.0 International (CC BY 4.0)** license.

The soap image used as a visual support in the demonstration project was generated using OpenAI image generation specifically for ANNA. It is distributed as part of the ANNA demonstration materials.

These terms apply only to the corresponding demonstration resources and do not replace the ANNA software license.

## Research data

ANNA can optionally record structured information during research sessions.

Research-session data are stored separately from ANNA project files. Session records may include:

- `session.json`
- `events.jsonl`
- `summary.json`

Research data can also be exported to CSV files for subsequent analysis.

For information about local data storage, participant information, anonymized exports, and privacy-related considerations, see [`DATA_PRIVACY.md`](DATA_PRIVACY.md).

## Testing

ANNA 1.0.0 includes an automated test suite implemented with pytest.

The release version was validated with **312 automated tests across 53 test modules**. All 312 tests passed during final validation.

The test suite is available in the `tests` directory.

To run the tests:

```bash
python -m pytest -q
```

## Project structure

Key files and directories include:

- `assets/` — application resources.
- `demo_project/` — demonstration project and associated materials.
- `licenses/` — licensing information for distributed resources.
- `packaging/` — packaging and executable-validation utilities.
- `tests/` — automated test suite.
- `ANNA.spec` — PyInstaller configuration for the Windows distribution.
- `DATA_PRIVACY.md` — information about data storage and research-session data.
- `RESOURCE_INVENTORY.md` — inventory of distributed resources.
- `THIRD_PARTY_NOTICES.txt` — third-party notices.
- `requirements.txt` — runtime Python dependencies.
- `requirements-dev.txt` — development and testing dependencies.

## License

ANNA software is distributed under the **GNU General Public License v3.0 or later (GPL-3.0-or-later)**.

See [`LICENSE`](LICENSE) for the complete license text.

Demonstration media and third-party components may be subject to separate licensing terms. See [`THIRD_PARTY_NOTICES.txt`](THIRD_PARTY_NOTICES.txt), [`RESOURCE_INVENTORY.md`](RESOURCE_INVENTORY.md), and the `licenses` directory for additional information.

## Support and issues

Problems, reproducible bugs, and other software-related issues can be reported through the GitHub Issues section of this repository.

When reporting a problem, please include the ANNA version, Windows version, a description of the issue, and the steps required to reproduce it when possible.

## Citation

Citation information and the archived release DOI will be added after publication of the ANNA 1.0.0 release.