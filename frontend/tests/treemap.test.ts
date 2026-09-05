import { describe, expect, it } from "vitest";
import { squarify } from "@/lib/treemap";

describe("squarify", () => {
  it("returns no tiles for an empty or zero-sized input", () => {
    expect(squarify([], 100, 100)).toEqual([]);
    expect(squarify([{ key: "A", value: 1 }], 0, 100)).toEqual([]);
  });

  it("drops non-positive values", () => {
    const tiles = squarify(
      [
        { key: "A", value: 10 },
        { key: "B", value: 0 },
        { key: "C", value: -5 },
      ],
      100,
      100,
    );
    expect(tiles.map((t) => t.item.key)).toEqual(["A"]);
  });

  it("fills the box and sizes tiles proportionally", () => {
    const tiles = squarify(
      [
        { key: "BIG", value: 75 },
        { key: "SMALL", value: 25 },
      ],
      200,
      100,
    );
    const area = (k: string) => {
      const t = tiles.find((x) => x.item.key === k)!;
      return t.width * t.height;
    };
    expect(tiles).toHaveLength(2);
    expect(area("BIG") + area("SMALL")).toBeCloseTo(200 * 100, 4);
    expect(area("BIG") / area("SMALL")).toBeCloseTo(3, 4);
  });

  it("orders tiles largest first and keeps them inside the box", () => {
    const tiles = squarify(
      [
        { key: "A", value: 5 },
        { key: "B", value: 40 },
        { key: "C", value: 20 },
        { key: "D", value: 35 },
      ],
      300,
      180,
    );
    expect(tiles[0].item.key).toBe("B");
    for (const t of tiles) {
      expect(t.x).toBeGreaterThanOrEqual(-1e-6);
      expect(t.y).toBeGreaterThanOrEqual(-1e-6);
      expect(t.x + t.width).toBeLessThanOrEqual(300 + 1e-6);
      expect(t.y + t.height).toBeLessThanOrEqual(180 + 1e-6);
    }
  });
});
