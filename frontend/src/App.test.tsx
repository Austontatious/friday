import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";

const mockNavigate = jest.fn();
const mockSendPrompt = jest.fn();
const mockConfirmMemory = jest.fn();
const mockGetStoredChatMode = jest.fn(() => "direct_friday");
const mockSetStoredChatMode = jest.fn();

jest.mock("@chakra-ui/react", () => {
  const React = require("react");
  const makeElement = (tag: string) =>
    React.forwardRef(({ as, children, isDisabled, ...props }: any, ref: React.Ref<HTMLElement>) =>
      React.createElement(as || tag, { ...props, ref, disabled: isDisabled }, children),
    );

  const Textarea = React.forwardRef(({ children, ...props }: any, ref: React.Ref<HTMLTextAreaElement>) =>
    React.createElement("textarea", { ...props, ref }, children),
  );

  const useColorMode = () => {
    const [colorMode, setColorMode] = React.useState("light");
    return {
      colorMode,
      toggleColorMode: () => setColorMode((mode: string) => (mode === "light" ? "dark" : "light")),
    };
  };

  const useToast = () => () => undefined;

  return {
    Badge: makeElement("span"),
    Box: makeElement("div"),
    Button: makeElement("button"),
    HStack: makeElement("div"),
    IconButton: makeElement("button"),
    Text: makeElement("span"),
    Textarea,
    VStack: makeElement("div"),
    useColorMode,
    useToast,
  };
});

jest.mock("./services/api", () => ({
  confirmMemory: (...args: unknown[]) => mockConfirmMemory(...args),
  getStoredChatMode: () => mockGetStoredChatMode(),
  sendPrompt: (...args: unknown[]) => mockSendPrompt(...args),
  setStoredChatMode: (...args: unknown[]) => mockSetStoredChatMode(...args),
}));

jest.mock(
  "@chakra-ui/icons",
  () => ({
    MoonIcon: () => null,
    SunIcon: () => null,
  }),
  { virtual: true },
);

jest.mock(
  "react-router-dom",
  () => ({
    useNavigate: () => mockNavigate,
  }),
  { virtual: true },
);

const renderApp = () => render(<App />);

describe("FRIDAY shell", () => {
  beforeEach(() => {
    window.localStorage.clear();
    process.env.REACT_APP_DEFAULT_MODE = "direct_friday";
    delete process.env.REACT_APP_SKETCHMATH_ENABLED;
    mockNavigate.mockClear();
    mockSendPrompt.mockReset();
    mockConfirmMemory.mockReset();
    mockGetStoredChatMode.mockClear();
    mockSetStoredChatMode.mockClear();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: jest.fn(),
    });
  });

  it("renders SketchMath by default and keeps Direct Friday visible", () => {
    renderApp();

    expect(screen.queryByRole("button", { name: "Althing" })).toBeNull();
    expect(screen.getByRole("button", { name: "Direct Friday" })).toBeVisible();
    expect(screen.getByRole("button", { name: "SUBMIT" })).toBeVisible();
    expect(screen.getByRole("button", { name: "SketchMath" })).toBeVisible();
    expect(screen.getByTestId("friday-telemetry-panel")).toBeVisible();
    expect(screen.getByTestId("friday-session-map")).toBeVisible();
  });

  it("renders Direct Friday and hides SketchMath when the feature flag is off", () => {
    process.env.REACT_APP_SKETCHMATH_ENABLED = "0";

    renderApp();

    expect(screen.queryByRole("button", { name: "Althing" })).toBeNull();
    expect(screen.getByRole("button", { name: "Direct Friday" })).toBeVisible();
    expect(screen.getByRole("button", { name: "SUBMIT" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "SketchMath" })).toBeNull();
  });

  it("renders SketchMath when the feature flag is on", () => {
    process.env.REACT_APP_SKETCHMATH_ENABLED = "1";

    renderApp();

    expect(screen.queryByRole("button", { name: "Althing" })).toBeNull();
    expect(screen.getByRole("button", { name: "Direct Friday" })).toBeVisible();
    expect(screen.getByRole("button", { name: "SUBMIT" })).toBeVisible();
    expect(screen.getByRole("button", { name: "SketchMath" })).toBeVisible();
  });

  it("navigates to the SketchMath route when clicked", async () => {
    process.env.REACT_APP_SKETCHMATH_ENABLED = "1";

    renderApp();

    await userEvent.click(screen.getByRole("button", { name: "SketchMath" }));

    expect(mockNavigate).toHaveBeenCalledWith("/tools/sketchmath");
  });

  it("renders the Direct Friday chat flow when submitting a prompt", async () => {
    process.env.REACT_APP_SKETCHMATH_ENABLED = "1";
    mockSendPrompt.mockResolvedValue({
      text: "Direct Friday reply",
      meta: {
        model: "local-test-model",
        context_usage: { used: 1200, limit: 4096 },
      },
    });

    renderApp();

    await userEvent.type(screen.getByPlaceholderText("Ask FRIDAY something..."), "hello friday");
    await userEvent.click(screen.getByRole("button", { name: "SUBMIT" }));

    expect((await screen.findAllByText("hello friday"))[0]).toBeVisible();
    expect((await screen.findAllByText("Direct Friday reply"))[0]).toBeVisible();
    expect((await screen.findAllByText(/local-test-model/))[0]).toBeVisible();
    expect(mockSendPrompt).toHaveBeenCalled();
  });

  it("renders assistant markdown as document content", async () => {
    mockSendPrompt.mockResolvedValue({
      assistant_text: "## Plan\n\n- Inspect shell\n- Ship `telemetry`\n\n> Keep the sidecar quiet.\n\n```ts\nconst ok = true;\n```",
    });

    renderApp();

    await userEvent.type(screen.getByPlaceholderText("Ask FRIDAY something..."), "show markdown");
    await userEvent.click(screen.getByRole("button", { name: "SUBMIT" }));

    expect(await screen.findByRole("heading", { name: "Plan" })).toBeVisible();
    expect(await screen.findByText("Inspect shell")).toBeVisible();
    expect(await screen.findByText("telemetry")).toBeVisible();
    expect(await screen.findByText("Keep the sidecar quiet.")).toBeVisible();
    expect(await screen.findByText("const ok = true;")).toBeVisible();
  });

  it("routes failed requests into system events instead of assistant content", async () => {
    mockSendPrompt.mockRejectedValue(new Error("HTTP 503: backend offline"));

    renderApp();

    await userEvent.type(screen.getByPlaceholderText("Ask FRIDAY something..."), "fail please");
    await userEvent.click(screen.getByRole("button", { name: "SUBMIT" }));

    expect(await screen.findByText("Request failed")).toBeVisible();
    expect(await screen.findByText("HTTP 503: backend offline")).toBeVisible();
    expect(screen.queryByText("[Direct Friday request failed.]")).toBeNull();
  });
});
