// Minimal Solidity highlighter: comments, strings, hex literals, numbers, keywords, types.
(function (g) {
  const KW = new Set("pragma solidity contract library interface function modifier returns return if else for while do require revert assert emit event error struct mapping memory storage calldata public private internal external view pure payable constant immutable override virtual new delete using is constructor unchecked abi true false".split(" "));
  const TY = /^(u?int\d*|bytes\d*|bool|address|string)$/;
  const BUILTIN = new Set("block msg tx keccak256 ripemd160 sha256 ecrecover gasleft blockhash type this".split(" "));
  const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const RE = /(\/\/[^\n]*|\/\*[\s\S]*?\*\/)|("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|\b(hex"[0-9a-fA-F]*")|\b(0x[0-9a-fA-F_]+|\d[\d_]*(?:\.\d+)?(?:e\d+)?)\b|([A-Za-z_$][\w$]*)/g;
  function highlight(src) {
    let out = "", last = 0, m;
    RE.lastIndex = 0;
    while ((m = RE.exec(src))) {
      out += esc(src.slice(last, m.index));
      const [t, cm, str, hx, num, id] = m;
      if (cm) out += `<span class="tok-cm">${esc(t)}</span>`;
      else if (str || hx) out += `<span class="tok-str">${esc(t)}</span>`;
      else if (num) out += `<span class="tok-num">${esc(t)}</span>`;
      else if (id) {
        if (KW.has(id)) out += `<span class="tok-kw">${id}</span>`;
        else if (TY.test(id)) out += `<span class="tok-ty">${id}</span>`;
        else if (BUILTIN.has(id)) out += `<span class="tok-fn">${id}</span>`;
        else out += esc(id);
      } else out += esc(t);
      last = RE.lastIndex;
    }
    return out + esc(src.slice(last));
  }
  g.solHighlight = highlight;
})(typeof window !== "undefined" ? window : globalThis);
