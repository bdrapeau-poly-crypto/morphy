import { describe, it, expect } from "vitest";

import { normalizeUsername } from "../context/UsernameContext.jsx";

describe("normalizeUsername", () => {
  it("lowercases and trims a plain handle", () => {
    expect(normalizeUsername("  GothamChess ")).toBe("gothamchess");
  });

  it("keeps underscores and hyphens", () => {
    expect(normalizeUsername("my_chess-name")).toBe("my_chess-name");
  });

  it("extracts the handle from a pasted profile URL", () => {
    expect(normalizeUsername("https://www.chess.com/member/GothamChess")).toBe("gothamchess");
    expect(normalizeUsername("chess.com/member/hikaru/")).toBe("hikaru");
    expect(normalizeUsername("https://www.chess.com/member/GothamChess?tab=stats")).toBe("gothamchess");
  });

  it("strips characters Chess.com handles never contain", () => {
    expect(normalizeUsername("some name!")).toBe("somename");
  });
});
