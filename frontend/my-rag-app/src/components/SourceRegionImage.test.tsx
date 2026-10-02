import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import SourceRegionImage from "./SourceRegionImage";
const request = vi.hoisted(() => vi.fn());
vi.mock("../services/apiClient", () => ({ apiRequest: request }));
const source = { id: "chunk-1", documentId: "doc-1", title: "Insurance.pdf", visualQuery: "Show commitments image" };
beforeEach(() => request.mockReset());

it("shows actual image with filename and page from authenticated endpoint", async () => {
  request.mockResolvedValue({ image: "data:image/png;base64,test", filename: "Insurance.pdf", page: 24, width: 400, height: 200 });
  render(<SourceRegionImage source={source} isFa={false} />);
  expect(await screen.findByRole("img")).toHaveAttribute("alt", "Insurance.pdf · Page 24");
  expect(screen.getByText("Page 24")).toBeInTheDocument();
  expect(request).toHaveBeenCalledWith("/documents/doc-1/source-region", expect.objectContaining({ method: "POST", body: JSON.stringify({ chunk_id: "chunk-1", query: source.visualQuery }), signal: expect.any(AbortSignal) }));
});

it("shows unavailable images inline and supports retry", async () => {
  request.mockRejectedValueOnce(new Error("Source region unavailable"));
  request.mockResolvedValueOnce({ image: "data:image/png;base64,test", filename: "Insurance.pdf", page: 1, width: 400, height: 200 });
  render(<SourceRegionImage source={source} isFa={false} />);
  expect(await screen.findByText("Source region unavailable")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Retry image" }));
  await waitFor(() => expect(screen.getByRole("img")).toBeInTheDocument());
});
