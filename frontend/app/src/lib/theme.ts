export type Theme = "light" | "dark";

export const THEME_STORAGE_KEY = "theme";

export function getPreferredTheme(): Theme {
  const savedTheme = localStorage.getItem(THEME_STORAGE_KEY);
  if (savedTheme === "light" || savedTheme === "dark") return savedTheme;
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function saveTheme(theme: Theme): void {
  localStorage.setItem(THEME_STORAGE_KEY, theme);
}
