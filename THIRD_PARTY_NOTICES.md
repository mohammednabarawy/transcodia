# Third-party components

Transcodia's project-specific application code, interface and artwork are maintained separately from the libraries they use. The project does not claim ownership of dependency code, trademarks, or license texts.

| Component | Purpose | Upstream license information |
| --- | --- | --- |
| Python | Application runtime | [PSF license](https://docs.python.org/3/license.html) |
| PySide6 / Qt | Desktop widgets and rendering | [Qt for Python licenses](https://doc.qt.io/qtforpython-6/licenses.html); open-source LGPL option for the modules used |
| pypdf | PDF structure, merge and text extraction | [BSD-3-Clause](https://github.com/py-pdf/pypdf/blob/main/LICENSE) |
| pdfplumber / pdfminer.six | PDF table extraction | [pdfplumber license](https://github.com/jsvine/pdfplumber/blob/stable/LICENSE.txt), [pdfminer.six license](https://github.com/pdfminer/pdfminer.six/blob/master/LICENSE) |
| pypdfium2 / PDFium | Page previews | [License and dependency notices](https://github.com/pypdfium2-team/pypdfium2/blob/main/LICENSES/README.md) |
| ReportLab | Text-oriented PDF output | [ReportLab license](https://hg.reportlab.com/hg-public/reportlab/file/tip/LICENSE.txt) |
| Pillow | Image conversion | [Pillow license](https://github.com/python-pillow/Pillow/blob/main/LICENSE) |
| openpyxl | XLSX output | [openpyxl license](https://openpyxl.readthedocs.io/en/stable/index.html) |
| python-docx | DOCX reading and writing | [python-docx license](https://github.com/python-openxml/python-docx/blob/master/LICENSE) |
| psutil | Conversion-process controls | [psutil license](https://github.com/giampaolo/psutil/blob/master/LICENSE) |

Transitive libraries retain their own licenses. Build scripts collect the installed runtime dependency versions and available upstream notice files into `THIRD_PARTY_LICENSES/manifest.json` and adjacent folders inside the desktop distribution. The source repository does not vendor dependency implementations or executable libraries.

FFmpeg is an independently installed command-line dependency, invoked as a separate process. Transcodia's default desktop distributions do not redistribute it. Its license depends on how that executable was built; obtain it from its distributor and follow [upstream licensing guidance](https://ffmpeg.org/legal.html). The application does not claim ownership of FFmpeg or its codecs.

Qt libraries remain dynamically loaded and replaceable in a desktop bundle. The included LGPL and GPL license texts document the selected LGPL terms and their referenced provisions; their presence does not license Transcodia's original project material under the GPL. Distributors must preserve notices and satisfy the applicable source-availability and replacement requirements. See the [Qt LGPL guidance](https://www.qt.io/licensing/open-source-lgpl-obligations).

The asset creation record is in [`_docs/asset_provenance.md`](_docs/asset_provenance.md). Newly generated artwork has not received an independent trademark-clearance opinion. This inventory and the automated checks describe technical evidence, not a legal certification.
