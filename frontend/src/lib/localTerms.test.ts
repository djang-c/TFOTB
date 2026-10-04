import { beforeEach, describe, expect, it } from "vitest";
import {
  getLocal,
  isLocalId,
  listLocal,
  removeLocal,
  saveLocal,
  searchLocal,
  updateNote,
} from "@/lib/localTerms";

beforeEach(() => window.localStorage.clear());

describe("terms kept on this device only", () => {
  it("saves once per name, labelled with the reason, and finds it again", () => {
    const a = saveLocal("Flight of the Buffalo", "not a MeSH heading");
    const b = saveLocal("flight of the  buffalo", "again");
    expect(a.id).toBe("LOCAL:flight-of-the-buffalo");
    expect(b.id).toBe(a.id);
    expect(listLocal()).toHaveLength(1);
    expect(isLocalId(a.id)).toBe(true);
    expect(searchLocal("buffalo").map((t) => t.label)).toEqual(["Flight of the Buffalo"]);
    expect(getLocal(a.id)?.reason).toBe("not a MeSH heading");
  });

  it("keeps a note and can delete", () => {
    const t = saveLocal("x term", "r");
    updateNote(t.id, "my note");
    expect(getLocal(t.id)?.note).toBe("my note");
    removeLocal(t.id);
    expect(listLocal()).toEqual([]);
  });

  it("survives blocked or corrupt storage instead of throwing", () => {
    window.localStorage.setItem("tfotb.localTerms.v1", "{not json");
    expect(listLocal()).toEqual([]);
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = () => {
      throw new Error("quota");
    };
    try {
      expect(() => saveLocal("y term", "r")).not.toThrow();
    } finally {
      Storage.prototype.setItem = original;
    }
  });
});
