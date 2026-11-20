// SPDX-License-Identifier: AGPL-3.0-or-later
import html2canvas from "html2canvas";
import { exportElementAsPNG } from "../exportElementAsPNG";

jest.mock("html2canvas", () => jest.fn());

const mockedHtml2canvas = html2canvas as unknown as jest.Mock;

describe("exportElementAsPNG", () => {
  let clicked: HTMLAnchorElement[];

  beforeEach(() => {
    clicked = [];
    mockedHtml2canvas.mockReset();
    mockedHtml2canvas.mockResolvedValue({
      toDataURL: jest.fn(() => "data:image/png;base64,AAAA"),
    });
    jest
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(function (this: HTMLAnchorElement) {
        clicked.push(this);
      });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("renders the element with the options of the replaced package", async () => {
    const element = document.createElement("div");
    await exportElementAsPNG(element, "widget.png");
    expect(mockedHtml2canvas).toHaveBeenCalledWith(element, {
      scrollY: -window.scrollY,
      useCORS: true,
    });
  });

  it("downloads the canvas as a full-quality PNG under the given name", async () => {
    await exportElementAsPNG(document.createElement("div"), "widget.png");
    const canvas = await mockedHtml2canvas.mock.results[0].value;
    expect(canvas.toDataURL).toHaveBeenCalledWith("image/png", 1);
    expect(clicked).toHaveLength(1);
    expect(clicked[0].download).toBe("widget.png");
    expect(clicked[0].href).toBe("data:image/png;base64,AAAA");
    expect(document.body.contains(clicked[0])).toBe(false);
  });

  it("does nothing without an element", async () => {
    await exportElementAsPNG(null, "widget.png");
    expect(mockedHtml2canvas).not.toHaveBeenCalled();
    expect(clicked).toHaveLength(0);
  });
});
