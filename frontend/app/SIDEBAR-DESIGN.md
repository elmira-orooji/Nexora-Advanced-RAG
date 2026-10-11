# Sidebar design

The sidebar is a local implementation using the project's existing React and Lucide dependencies. No third-party component code or new packages were installed.

References reviewed:
- 21st Dashboard Sidebar by arunjdass: https://21st.dev/@arunjdass/components/dashboard-sidebar — catalog reference for restrained dual-theme surfaces. Code retrieval was unavailable because the free daily quota was exhausted.
- shadcn/ui sidebar blocks: https://ui.shadcn.com/blocks/sidebar — reference for grouped navigation, a collapsible icon rail, and a separated account footer.

`src/styles/sidebar.css` owns scoped light/dark tokens. The existing violet brand accent is preserved. Conversation actions appear on hover or keyboard focus, and remain visible on touch devices. Navigation and history share a scroll region so controls remain accessible in short viewports. Reduced-motion preferences disable transitions.

Verification: production build and component ESLint passed. Browser visual verification was not performed because the existing browser URL policy blocks access.
