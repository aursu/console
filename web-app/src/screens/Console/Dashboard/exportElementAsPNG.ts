// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Saves a rendered element as a PNG file.
//
// Replaces exportComponentAsPNG from react-component-export-image, which
// shipped a prebuilt jsPDF (unused here: only the PNG export was called) with
// it. The rendering is the same: html2canvas with the options that package
// used, the PNG at full quality, saved through a temporary download link.
import html2canvas from "html2canvas";

export const exportElementAsPNG = async (
  element: HTMLElement | null,
  fileName: string,
): Promise<void> => {
  if (!element) {
    return;
  }
  const canvas = await html2canvas(element, {
    scrollY: -window.scrollY,
    useCORS: true,
  });
  const link = document.createElement("a");
  link.href = canvas.toDataURL("image/png", 1);
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};
