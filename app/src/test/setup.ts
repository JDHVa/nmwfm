import "@testing-library/jest-dom/vitest";

class RO {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = globalThis.ResizeObserver ?? (RO as unknown as typeof ResizeObserver);

if (!window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

HTMLCanvasElement.prototype.getContext = (() => null) as unknown as HTMLCanvasElement["getContext"];
Element.prototype.scrollIntoView = () => {};
let blobs = 0;
URL.createObjectURL = () => `blob:mock-${++blobs}`;

class IO {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return [];
  }
}
globalThis.IntersectionObserver =
  globalThis.IntersectionObserver ?? (IO as unknown as typeof IntersectionObserver);
