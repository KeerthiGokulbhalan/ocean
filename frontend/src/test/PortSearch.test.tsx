import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PortSearch from "../components/PortSearch";
import type { Port } from "../types";

const PORTS: Port[] = [
  {
    id: "IN_CHENNAI",
    name: "Chennai Port",
    display_name: "Chennai Port — Tamil Nadu",
    state: "Tamil Nadu",
    country: "India",
    latitude: 13.098,
    longitude: 80.293,
    port_type: "Major Port",
    port_code: "INMAA",
  },
  {
    id: "IN_KAMARAJAR",
    name: "Kamarajar Port",
    display_name: "Kamarajar Port — Tamil Nadu",
    state: "Tamil Nadu",
    country: "India",
    latitude: 13.25,
    longitude: 80.333,
    port_type: "Major Port",
    port_code: "INENR",
  },
  {
    id: "IN_MUMBAI",
    name: "Mumbai Port",
    display_name: "Mumbai Port — Maharashtra",
    state: "Maharashtra",
    country: "India",
    latitude: 18.95,
    longitude: 72.84,
    port_type: "Major Port",
    port_code: "INBOM",
  },
];

function setup(props: Partial<React.ComponentProps<typeof PortSearch>> = {}) {
  const onChange = vi.fn();
  render(
    <PortSearch
      label="Origin"
      value={null}
      onChange={onChange}
      ports={PORTS}
      {...props}
    />
  );
  return { onChange };
}

describe("PortSearch", () => {
  it("lists every port once opened", async () => {
    const user = userEvent.setup();
    setup();
    await user.click(screen.getByRole("combobox"));
    expect(screen.getAllByRole("option")).toHaveLength(3);
  });

  it("filters by partial port name", async () => {
    const user = userEvent.setup();
    setup();
    await user.type(screen.getByRole("combobox"), "chenn");
    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(1);
    expect(options[0]).toHaveTextContent("Chennai Port");
  });

  it("filters by state", async () => {
    const user = userEvent.setup();
    setup();
    await user.type(screen.getByRole("combobox"), "Tamil Nadu");
    expect(screen.getAllByRole("option")).toHaveLength(2);
  });

  it("filters by UN/LOCODE", async () => {
    const user = userEvent.setup();
    setup();
    await user.type(screen.getByRole("combobox"), "INBOM");
    expect(screen.getAllByRole("option")[0]).toHaveTextContent("Mumbai Port");
  });

  it("shows an empty state when nothing matches", async () => {
    const user = userEvent.setup();
    setup();
    await user.type(screen.getByRole("combobox"), "zzzz");
    expect(screen.queryAllByRole("option")).toHaveLength(0);
    expect(screen.getByText(/no ports match/i)).toBeInTheDocument();
  });

  it("selects a port by click", async () => {
    const user = userEvent.setup();
    const { onChange } = setup();
    await user.click(screen.getByRole("combobox"));
    await user.click(screen.getByText("Mumbai Port"));
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ id: "IN_MUMBAI" }));
  });

  it("selects a port with arrow keys and Enter", async () => {
    const user = userEvent.setup();
    const { onChange } = setup();
    const input = screen.getByRole("combobox");
    await user.click(input);
    await user.keyboard("{ArrowDown}{Enter}");
    // first ArrowDown moves from index 0 to index 1
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ id: "IN_KAMARAJAR" }));
  });

  it("moves the highlight back up with ArrowUp", async () => {
    const user = userEvent.setup();
    const { onChange } = setup();
    await user.click(screen.getByRole("combobox"));
    await user.keyboard("{ArrowDown}{ArrowDown}{ArrowUp}{Enter}");
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ id: "IN_KAMARAJAR" }));
  });

  it("closes the list on Escape without selecting", async () => {
    const user = userEvent.setup();
    const { onChange } = setup();
    await user.click(screen.getByRole("combobox"));
    expect(screen.getAllByRole("option").length).toBeGreaterThan(0);
    await user.keyboard("{Escape}");
    expect(screen.queryAllByRole("option")).toHaveLength(0);
    expect(onChange).not.toHaveBeenCalled();
  });

  it("marks the active option with aria-activedescendant", async () => {
    const user = userEvent.setup();
    setup();
    const input = screen.getByRole("combobox");
    await user.click(input);
    expect(input).toHaveAttribute("aria-activedescendant");
    const options = screen.getAllByRole("option");
    expect(options[0]).toHaveAttribute("aria-selected", "true");
  });

  it("excludes the port already chosen on the other field", async () => {
    const user = userEvent.setup();
    setup({ excludePortId: "IN_MUMBAI" });
    await user.click(screen.getByRole("combobox"));
    expect(screen.queryByText("Mumbai Port")).not.toBeInTheDocument();
    expect(screen.getAllByRole("option")).toHaveLength(2);
  });

  it("renders the selected port with state and type, and can clear it", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <PortSearch label="Origin" value={PORTS[0]} onChange={onChange} ports={PORTS} />
    );
    expect(screen.getByText("Chennai Port")).toBeInTheDocument();
    expect(screen.getByText(/Tamil Nadu · Major Port/)).toBeInTheDocument();

    await user.click(screen.getByLabelText("Clear Origin"));
    expect(onChange).toHaveBeenCalledWith(null);
  });

  it("surfaces a validation error", () => {
    render(
      <PortSearch
        label="Origin"
        value={PORTS[0]}
        onChange={vi.fn()}
        ports={PORTS}
        error="Origin and destination must be different ports."
      />
    );
    expect(screen.getByText(/must be different ports/i)).toBeInTheDocument();
  });

  it("disables input while ports are loading", () => {
    setup({ loading: true });
    expect(screen.getByRole("combobox")).toBeDisabled();
  });
});
