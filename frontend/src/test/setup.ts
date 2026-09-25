import "@testing-library/jest-dom/vitest";

// jsdom implements neither of these, and Leaflet + the tracking hook both
// reach for them during render.
if (!window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

if (!window.scrollTo) {
  window.scrollTo = () => {};
}

// Element.prototype.scrollIntoView is used by the port dropdown's keyboard
// navigation to keep the active option visible.
Element.prototype.scrollIntoView = Element.prototype.scrollIntoView ?? (() => {});
