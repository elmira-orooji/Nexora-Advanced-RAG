import { useEffect, type RefObject } from "react";

const DURATION_MS = 100;
const ITEM_LEAD_MS = DURATION_MS / 3;
const SECTION_SELECTOR = ":scope > *:not(aside):not(dialog):not([role='dialog'])";

function visualItems(section: HTMLElement): HTMLElement[] {
  let scope = section;

  // Pages use small structural wrappers. Descend through a single wrapper so
  // the animation is applied to actual visual groups rather than one full page.
  for (let depth = 0; depth < 3; depth += 1) {
    const children = Array.from(scope.querySelectorAll<HTMLElement>(SECTION_SELECTOR));
    if (children.length !== 1) return children.length ? children : [scope];
    scope = children[0];
  }

  return [scope];
}

/**
 * Gives each routed page one calm entrance sequence. Content remains visible
 * until JavaScript has painted twice, so navigation is never blocked by motion.
 */
export function useEntranceMotion(rootRef: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    const timers = new Set<number>();
    const observed = new WeakSet<HTMLElement>();
    const queued = new Set<HTMLElement>();
    let frameOne = 0;
    let frameTwo = 0;
    let queueFrame = 0;
    let ready = false;

    const reveal = (section: HTMLElement) => {
      if (section.dataset.entranceState === "revealed") return;
      section.dataset.entranceState = "revealed";
      visualItems(section).forEach((item, index) => {
        item.style.setProperty("--entrance-delay", `${index * ITEM_LEAD_MS}ms`);
        const timer = window.setTimeout(() => {
          item.classList.add("entrance-motion-visible");
          timers.delete(timer);
        }, index * ITEM_LEAD_MS);
        timers.add(timer);
      });
    };

    const flushQueue = () => {
      queueFrame = 0;
      [...queued]
        .sort((left, right) => left.compareDocumentPosition(right) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1)
        .forEach(reveal);
      queued.clear();
    };

    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const section = entry.target as HTMLElement;
        observer.unobserve(section);
        queued.add(section);
      });
      if (!queueFrame && queued.size) queueFrame = window.requestAnimationFrame(flushQueue);
    }, { threshold: 0.08, rootMargin: "0px 0px -8% 0px" });

    const prepare = () => {
      if (!ready || reduced.matches) return;
      const section = Array.from(root.children).find((element) => element instanceof HTMLElement) as HTMLElement | undefined;
      if (!section || observed.has(section)) return;
      observed.add(section);
      section.dataset.entranceSection = "";
      visualItems(section).forEach((item) => item.classList.add("entrance-motion-pending"));
      observer.observe(section);
    };

    const mutationObserver = new MutationObserver(prepare);
    const setReduced = () => {
      root.dataset.entranceMotion = reduced.matches ? "reduced" : "enabled";
      if (reduced.matches) {
        root.querySelectorAll<HTMLElement>(".entrance-motion-pending").forEach((item) => {
          item.classList.remove("entrance-motion-pending", "entrance-motion-visible");
          item.style.removeProperty("--entrance-delay");
        });
      } else prepare();
    };

    setReduced();
    mutationObserver.observe(root, { childList: true });
    frameOne = window.requestAnimationFrame(() => {
      frameTwo = window.requestAnimationFrame(() => {
        ready = true;
        prepare();
      });
    });
    reduced.addEventListener("change", setReduced);

    return () => {
      window.cancelAnimationFrame(frameOne);
      window.cancelAnimationFrame(frameTwo);
      window.cancelAnimationFrame(queueFrame);
      observer.disconnect();
      mutationObserver.disconnect();
      reduced.removeEventListener("change", setReduced);
      timers.forEach((timer) => window.clearTimeout(timer));
    };
  }, [rootRef]);
}
