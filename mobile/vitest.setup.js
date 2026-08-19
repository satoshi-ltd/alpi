import { vi } from "vitest";

// react-native imports resolve to a tiny shim so libs that pull `import {Platform} from 'react-native'` don't blow up under jsdom. The hook tests we run here don't render RN components — they exercise pure JS state machines.
vi.mock("react-native", () => ({
  Platform: { OS: "ios", select: (sel) => sel?.ios ?? sel?.default },
  AppState: { addEventListener: () => ({ remove: () => {} }), currentState: "active" },
  Linking: { openURL: vi.fn(async () => true) },
}));

// react-native-svg ships untranspiled — importing Icon is a parse error without this
vi.mock("react-native-svg", async () => {
  const React = await import("react");
  const el = (tag) => ({ children, ...props }) => React.createElement(tag, props, children);
  return {
    default: el("svg"),
    Svg: el("svg"),
    Circle: el("circle"),
    Defs: el("defs"),
    G: el("g"),
    Line: el("line"),
    LinearGradient: el("linearGradient"),
    Path: el("path"),
    Polyline: el("polyline"),
    Rect: el("rect"),
    Stop: el("stop"),
  };
});

vi.mock("expo-router", () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn(), replace: vi.fn(), canGoBack: () => false }),
  usePathname: () => "/",
  useLocalSearchParams: () => ({}),
  useFocusEffect: (fn) => { fn?.(); },
  useNavigation: () => ({ setOptions: vi.fn(), addListener: () => () => {}, dispatch: vi.fn() }),
}));

vi.mock("expo-secure-store", () => ({
  getItemAsync: vi.fn(async () => null),
  setItemAsync: vi.fn(async () => {}),
  deleteItemAsync: vi.fn(async () => {}),
}));
