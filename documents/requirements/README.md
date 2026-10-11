# SRS source and PDF

`Nexora-SRS.docx` is the editable source for `Nexora-SRS.pdf`. It preserves the university cover, typography, tables, and footer of the formatted original. Technical references and operation-feedback requirements were updated on 2026-10-11.

On Windows with Microsoft Word installed, export from the repository root:

```powershell
./documents/scripts/export_srs_pdf.ps1 -Output ./documents/requirements/Nexora-SRS.pdf
```

The exporter runs its own hidden Word instance, updates the manually styled contents page and fields, and closes only that instance. Review rendered pages after changing content; do not assume a successful export guarantees layout quality.

`documents/scripts/update_srs_source.py` migrates an original formatted SRS to this source. It is a one-time migration, not the normal PDF-export command. The separate `build_srs_expanded.py` builds an alternative expanded draft and does not reproduce the university template.
