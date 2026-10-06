import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Composer from "./Composer.jsx";

const MENTIONS = [{ id: "quill", hint: "writer" }];

function setup(props = {}) {
  const view = render(<Composer value="" onChange={() => {}} mentions={MENTIONS} minHeight={40} {...props} />);
  const ta = screen.getByRole("textbox");
  const again = (next) =>
    view.rerender(<Composer value={next} onChange={() => {}} mentions={MENTIONS} minHeight={40} {...props} />);
  return { ta, again };
}

describe("Composer while a composition is open", () => {
  it("control: sizes itself on a plain value change", () => {
    const { ta, again } = setup();
    ta.style.height = "77px";
    again("hello");
    expect(ta.style.height).toBe("40px");
  });

  it("leaves the textarea style alone until the composition ends", () => {
    const { ta, again } = setup();
    ta.style.height = "77px";
    fireEvent.compositionStart(ta);
    again("hello there");
    again("hello there, dictated");
    expect(ta.style.height).toBe("77px");
    fireEvent.compositionEnd(ta);
    expect(ta.style.height).toBe("40px");
  });

  it("opens the mention popover only after the composition ends", () => {
    const { ta, again } = setup();
    fireEvent.compositionStart(ta);
    again("@qu");
    ta.setSelectionRange(3, 3);
    fireEvent.select(ta);
    expect(screen.queryByRole("listbox")).toBeNull();
    fireEvent.compositionEnd(ta);
    expect(screen.getByRole("listbox")).toBeInTheDocument();
  });

  it("keeps focus on the field across mid-composition re-renders", () => {
    const { ta, again } = setup();
    ta.focus();
    fireEvent.compositionStart(ta);
    again("spoken");
    again("spoken words");
    expect(document.activeElement).toBe(ta);
  });

  it("closes an open popover when a composition starts", () => {
    const { ta, again } = setup();
    again("@qu");
    ta.setSelectionRange(3, 3);
    fireEvent.select(ta);
    expect(screen.getByRole("listbox")).toBeInTheDocument();
    fireEvent.compositionStart(ta);
    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("a blur that loses compositionend does not freeze sizing", () => {
    const { ta, again } = setup();
    fireEvent.compositionStart(ta);
    fireEvent.blur(ta);
    ta.style.height = "77px";
    again("after the blur");
    expect(ta.style.height).toBe("40px");
  });

  it("disabling the field mid-composition releases the guard", () => {
    const view = render(<Composer value="" onChange={() => {}} mentions={MENTIONS} minHeight={40} />);
    const ta = screen.getByRole("textbox");
    fireEvent.compositionStart(ta);
    view.rerender(<Composer value="sending" disabled onChange={() => {}} mentions={MENTIONS} minHeight={40} />);
    ta.style.height = "77px";
    view.rerender(<Composer value="" disabled onChange={() => {}} mentions={MENTIONS} minHeight={40} />);
    expect(ta.style.height).toBe("40px");
  });

  it("keeps mentions working once the text has landed", () => {
    const { ta, again } = setup();
    again("@qu");
    ta.setSelectionRange(3, 3);
    fireEvent.select(ta);
    expect(screen.getByRole("listbox")).toBeInTheDocument();
  });
});
