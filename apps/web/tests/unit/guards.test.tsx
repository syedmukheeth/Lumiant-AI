import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ErrorState } from "@/components/data/widget";
import { navFor, sectionFor } from "@/components/shell/nav";
import { ApiError } from "@/lib/api";

describe("route sections (direct URL protection)", () => {
  it("maps every page path, including sub-paths, to its section", () => {
    expect(sectionFor("/costs")?.section).toBe("costs");
    expect(sectionFor("/costs/anything")?.section).toBe("costs");
    expect(sectionFor("/admin")?.section).toBe("admin");
    expect(sectionFor("/explore")?.section).toBe("overview");
    expect(sectionFor("/costsheet")).toBeUndefined();
    expect(sectionFor("/login")).toBeUndefined();
  });

  it("a role without the costs section gets no Costs entry and the page is outside its sections", () => {
    const sections = ["overview", "inventory", "risks", "assistant", "reports"];
    expect(navFor(sections).map((n) => n.href)).not.toContain("/costs");
    expect(sections.includes(sectionFor("/costs")!.section)).toBe(false);
  });
});

describe("ErrorState", () => {
  it("shows a data gap (409) as 'Needs more data' with no error reference", () => {
    render(<ErrorState error={new ApiError(409, "capability_unavailable", "This analysis needs lot expiry dates.", "abcdef123456789")} />);
    expect(screen.getByTestId("data-gap")).toHaveTextContent("Needs more data");
    expect(screen.getByText("This analysis needs lot expiry dates.")).toBeInTheDocument();
    expect(screen.queryByText(/ref/)).toBeNull();
    expect(screen.queryByText("Could not load this")).toBeNull();
  });

  it("still reports real failures as errors", () => {
    render(<ErrorState error={new ApiError(500, "internal", "Something broke.", "abcdef123456789")} />);
    expect(screen.getByText("Could not load this")).toBeInTheDocument();
  });
});
