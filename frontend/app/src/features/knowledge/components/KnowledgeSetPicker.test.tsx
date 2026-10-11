import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import KnowledgeSetPicker, { ALL_KNOWLEDGE_SETS } from "./KnowledgeSetPicker";

it("keeps multiple selections open and lets all reset the scope", () => {
  function Harness() {
    const [value, setValue] = useState([ALL_KNOWLEDGE_SETS]);
    return <KnowledgeSetPicker sets={[{ id: "a", name: "Insurance" }, { id: "b", name: "Company" }]} value={value} onChange={setValue} isFa={false} />;
  }
  render(<Harness />);
  const trigger = screen.getByRole("button", { name: "Select knowledge bases" });
  fireEvent.click(trigger);
  fireEvent.click(screen.getByRole("checkbox", { name: "Insurance" }));
  fireEvent.click(screen.getByRole("checkbox", { name: "Company" }));
  expect(screen.getByRole("checkbox", { name: "Insurance" })).toBeChecked();
  expect(screen.getByRole("checkbox", { name: "Company" })).toBeChecked();
  expect(screen.getByRole("checkbox", { name: "All knowledge bases" })).not.toBeChecked();
  fireEvent.click(screen.getByRole("checkbox", { name: "All knowledge bases" }));
  expect(screen.getByRole("checkbox", { name: "Insurance" })).not.toBeChecked();
  fireEvent.keyDown(document, { key: "Escape" });
  expect(screen.queryByRole("group")).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
});
