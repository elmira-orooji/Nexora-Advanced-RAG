# Login design references

## Selected direction

- [shadcn/ui login blocks](https://ui.shadcn.com/blocks/login): free, open-source reference for the centered brand and heading, explicit field labels, restrained card, and one primary action. These patterns are implemented in the existing React form; no new registry package was installed or source copied verbatim.
- [tweakcn](https://github.com/jnsahaj/tweakcn): open-source theme editor and presets, useful for future token editing. No theme was imported: the requested Nexora violet and midnight palette remains unchanged.

## Other free options reviewed

- [blocks.so login blocks](https://blocks.so/login): free authentication layout alternatives.
- [Origin UI / coss ui](https://github.com/cosscom/coss): the legacy Origin UI and current UI directories have MIT licenses; other repository directories use AGPL. Origin is now a legacy snapshot with limited maintenance. Not installed in this project.

## Implementation constraints

Keep the existing hero image and its language-independent positioning, local fonts, RTL support, theme switch, viewport-based layout, and authentication service. Do not restore workspace selection, promotional copy, footer text, or unsupported authentication actions. The API still receives the default organization.

Changes are confined to login: centered logo and heading, consistent control spacing and radii, grouped appearance/language controls, focus/error/autofill feedback, and password visibility without losing pointer focus. Existing 21st references are retained in the stylesheet attribution.
