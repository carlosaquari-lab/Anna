# ANNA Resource Inventory

This document describes the main resources distributed with ANNA 1.0.0 and their licensing status.

## Software and documentation license

Copyright © 2026 Carlos Máñez-Carvajal

ANNA — Interactive Video Activities for AAC is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or any later version.

SPDX identifier: `GPL-3.0-or-later`.

This license applies to the ANNA source code and original documentation unless otherwise stated in a specific file. It does not automatically apply to videos, images, or other resources subject to separate terms. These materials are governed by the licenses or declarations specified in this inventory and in the demonstration project documentation.

| Path / resource | Type | Use | Source | Author / origin | License or terms | Status |
|---|---|---|---|---|---|---|
| `demo_project/videos/VID_20260906_121554.mp4` | Video | Washing Hands demonstration project | Original video | ANNA authors | CC BY 4.0 | Distributable |
| `demo_project/videos/VID_20260906_121715.mp4` | Video | Washing Hands demonstration project | Original video | ANNA authors | CC BY 4.0 | Distributable |
| Soap image used as a visual support | Image | Washing Hands demonstration project | Generated specifically for ANNA using OpenAI image generation | AI-generated using OpenAI image generation | Distributed as part of the ANNA demonstration materials | Distributable |
| Hotspot tool icons | Generated icons | Select/move, edit, delete, rectangle, and ellipse tools | Generated at runtime using `QPainter` in `hotspot_editor.py` | ANNA authors | Same license as the ANNA source code | Distributable |
| Mode-switching icons | Generated icons | Entering User mode and returning to Professional mode | Generated at runtime using `QPainter` in `hotspot_editor.py` | ANNA authors | Same license as the ANNA source code | Distributable |
| Playback icons | Standard Qt resources | Video play, pause, and stop controls | `QStyle.StandardPixmap` | The Qt Company and contributors | Applicable Qt/PySide6 licensing terms | Distributable subject to the Qt license |

## Publication status

The two videos included in the Washing Hands demonstration project were created by the ANNA authors and are distributed under the Creative Commons Attribution 4.0 International (CC BY 4.0) license, separately from the GPL license covering the software.

The soap image used as a visual support was generated using OpenAI image generation specifically for the ANNA demonstration project. Its origin is explicitly documented to distinguish it from both the GPL-licensed software and the videos created by the ANNA authors.

The interface icons do not depend on external image files: they are either generated using ANNA's own code or obtained at runtime from standard Qt resources.

Resources not required by the demonstration project are not included in the public distribution.

Resources used by the demonstration project are retained in the locations required by the current ANNA version so that the demonstration project can be opened and used directly.