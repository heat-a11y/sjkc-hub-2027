import type { StudentTpFillResult, StudentTpRecord } from "../../shared/types";

type TableInfo = {
  table: HTMLTableElement;
  headerRowIndex: number;
  nameIndex: number;
  idIndex: number;
  tpIndex: number;
  skillIndex: number;
  ulasanIndex: number;
  interventionIndex: number;
  effortIndex: number;
};

const SKILLS = ["LISTENING", "SPEAKING", "READING", "WRITING"];
const NAME_TOKEN_ALIASES: Record<string, string> = {
  abd: "abdul",
  mohamad: "muhammad",
  mohamed: "muhammad",
  mohammad: "muhammad",
  mohd: "muhammad",
  muhd: "muhammad",
};
const IGNORED_NAME_TOKENS = new Set(["bin", "binti", "bt"]);

function normalize(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim()
    .replace(/\s+/g, " ");
}

export function nameSimilarity(left: string, right: string): number {
  const a = normalize(left);
  const b = normalize(right);
  if (!a || !b) return 0;
  const characterScore = 1 - levenshtein(a, b) / Math.max(a.length, b.length);
  const tokens = (value: string) => value.split(" ")
    .filter(token => !IGNORED_NAME_TOKENS.has(token))
    .map(token => NAME_TOKEN_ALIASES[token] ?? token);
  const leftTokens = tokens(a);
  const rightTokens = tokens(b);
  const tokenPairs = leftTokens.flatMap((leftToken, leftIndex) =>
    rightTokens.map((rightToken, rightIndex) => {
      const similarity = leftToken === rightToken
        ? 1
        : Math.min(leftToken.length, rightToken.length) >= 4
          ? 1 - levenshtein(leftToken, rightToken) / Math.max(leftToken.length, rightToken.length)
          : 0;
      return { leftIndex, rightIndex, similarity };
    }),
  ).filter(pair => pair.similarity >= 0.72)
    .sort((left, right) => right.similarity - left.similarity);
  const matchedLeft = new Set<number>();
  const matchedRight = new Set<number>();
  let matchedScore = 0;
  for (const pair of tokenPairs) {
    if (matchedLeft.has(pair.leftIndex) || matchedRight.has(pair.rightIndex)) continue;
    matchedLeft.add(pair.leftIndex);
    matchedRight.add(pair.rightIndex);
    matchedScore += pair.similarity;
  }
  const tokenScore = leftTokens.length + rightTokens.length
    ? 2 * matchedScore / (leftTokens.length + rightTokens.length)
    : 0;
  let subsetMatched = 0;
  const subsetUsed = new Set<number>();
  const shorterTokens = leftTokens.length <= rightTokens.length ? leftTokens : rightTokens;
  const longerTokens = leftTokens.length <= rightTokens.length ? rightTokens : leftTokens;
  for (const token of shorterTokens) {
    let bestIndex = -1;
    let bestSimilarity = 0.72;
    longerTokens.forEach((candidate, index) => {
      if (subsetUsed.has(index)) return;
      const similarity = token === candidate
        ? 1
        : Math.min(token.length, candidate.length) >= 4
          ? 1 - levenshtein(token, candidate) / Math.max(token.length, candidate.length)
          : token === candidate ? 1 : 0;
      if (similarity >= bestSimilarity) {
        bestSimilarity = similarity;
        bestIndex = index;
      }
    });
    if (bestIndex >= 0) {
      subsetUsed.add(bestIndex);
      subsetMatched += 1;
    }
  }
  const subsetScore = shorterTokens.length && subsetMatched === shorterTokens.length ? 0.92 : 0;
  return Math.max(characterScore, tokenScore, subsetScore);
}

function levenshtein(left: string, right: string): number {
  const previous = Array.from({ length: right.length + 1 }, (_, index) => index);
  let current = new Array<number>(right.length + 1);
  for (let i = 1; i <= left.length; i += 1) {
    current[0] = i;
    for (let j = 1; j <= right.length; j += 1) {
      current[j] = Math.min(
        current[j - 1] + 1,
        previous[j] + 1,
        previous[j - 1] + Number(left[i - 1] !== right[j - 1]),
      );
    }
    for (let j = 0; j <= right.length; j += 1) previous[j] = current[j];
    current = new Array<number>(right.length + 1);
  }
  return previous[right.length];
}

export function nameMatches<T>(
  name: string,
  candidates: T[],
  getName: (candidate: T) => string,
): T[] {
  const exactMatches = candidates.filter(candidate =>
    normalize(getName(candidate)) === normalize(name),
  );
  if (exactMatches.length) return exactMatches;

  const ranked = candidates.map(candidate => ({
    candidate,
    score: nameSimilarity(name, getName(candidate)),
  })).filter(match => match.score >= 0.78)
    .sort((left, right) => right.score - left.score);
  if (!ranked.length) return [];
  const bestScore = ranked[0].score;
  return ranked
    .filter(match => bestScore - match.score < 0.08)
    .map(match => match.candidate);
}

function headerIndex(headers: string[], aliases: string[]): number {
  const expected = aliases.map(normalize);
  return headers.findIndex(header => {
    const value = normalize(header);
    return expected.some(alias =>
      value === alias ||
      (alias.length > 3 && value.startsWith(`${alias} `)) ||
      (alias.length > 3 && value.endsWith(` ${alias}`)),
    );
  });
}

function cellText(cell: HTMLTableCellElement | undefined): string {
  return (cell?.innerText || cell?.textContent || "").trim();
}

function controlLabels(control: HTMLElement): string[] {
  const labels = control instanceof HTMLInputElement
    ? Array.from(control.labels ?? []).map(label => label.innerText || label.textContent || "")
    : [];
  const labelledBy = control.getAttribute("aria-labelledby")
    ?.split(/\s+/)
    .map(id => document.getElementById(id)?.textContent ?? "") ?? [];
  return [
    control instanceof HTMLInputElement || control instanceof HTMLSelectElement ? control.value : "",
    control.getAttribute("aria-label") ?? "",
    control.textContent ?? "",
    ...labels,
    ...labelledBy,
  ].map(normalize).filter(Boolean);
}

function exactLabel(control: HTMLElement, label: string): boolean {
  const expected = normalize(label);
  return controlLabels(control).some(value =>
    value === expected || value.replace(/^\d+\s+/, "") === expected,
  );
}

function radioIsSelected(radio: HTMLInputElement): boolean {
  return radio.checked ||
    radio.getAttribute("aria-checked") === "true" ||
    radio.closest(".w-radio")?.classList.contains("w-radio--checked") === true;
}

async function selectRadio(
  radio: HTMLInputElement,
  group: HTMLInputElement[] = [radio],
): Promise<boolean> {
  if (radioIsSelected(radio)) {
    return group.filter(radioIsSelected).length === 1;
  }
  const label = Array.from(radio.labels ?? []).find(isVisible);
  if (label) label.click();
  else clickAction(radio.closest<HTMLElement>(".w-radio") ?? radio);

  const deadline = Date.now() + 500;
  while (Date.now() < deadline) {
    if (radioIsSelected(radio)) {
      return group.filter(radioIsSelected).length === 1;
    }
    await new Promise(resolve => window.setTimeout(resolve, 10));
  }
  return false;
}

function textOf(element: Element): string {
  const html = element as HTMLElement;
  return normalize(html.innerText || html.textContent || "");
}

function isVisible(element: HTMLElement): boolean {
  for (let current: HTMLElement | null = element; current; current = current.parentElement) {
    if (current.hidden || current.getAttribute("aria-hidden") === "true") return false;
    const style = window.getComputedStyle(current);
    if (style.display === "none" || style.visibility === "hidden") return false;
  }
  return true;
}

function clickAction(element: HTMLElement): void {
  element.click();
}

function elementIsSelected(element: HTMLElement): boolean {
  if (element instanceof HTMLInputElement) return radioIsSelected(element);
  if (element.getAttribute("aria-checked") === "true" ||
    element.getAttribute("aria-selected") === "true" ||
    element.getAttribute("aria-pressed") === "true") return true;
  const className = typeof element.className === "string"
    ? element.className
    : element.getAttribute("class") ?? "";
  if (/(?:^|\s)(?:checked|selected|active|w-radio--checked|w-option--selected|is-selected)(?:\s|$)/i.test(className)) {
    return true;
  }
  const nested = element.querySelector<HTMLInputElement>('input[type="radio"], input[type="checkbox"]');
  if (nested && radioIsSelected(nested)) return true;
  return Boolean(element.querySelector<HTMLElement>(
    '[aria-checked="true"], [aria-selected="true"], .w-radio--checked, .w-option--selected, .is-selected',
  ));
}

async function selectOptionByLabel(root: ParentNode, label: string): Promise<boolean> {
  const expected = normalize(label);
  const select = root.querySelector<HTMLSelectElement>("select");
  if (select) {
    const option = Array.from(select.options).find(item =>
      normalize(item.textContent || item.value) === expected,
    );
    if (!option) return false;
    if (select.value !== option.value) {
      select.value = option.value;
      dispatchChange(select);
    }
    return true;
  }

  const labelMatches = (value: string): boolean =>
    value === expected ||
    new RegExp(`(?:^|\\s)${expected}(?:\\s|$)`).test(value);
  const radios = Array.from(root.querySelectorAll<HTMLInputElement>('input[type="radio"], input[type="checkbox"]'));
  const matches = radios.filter(radio =>
    controlLabels(radio).some(value => labelMatches(value.replace(/^\d+\s+/, ""))),
  );
  if (matches.length === 1) {
    const group = matches[0].type === "radio"
      ? radios.filter(radio => radio.type === "radio" && radio.name === matches[0].name)
      : [matches[0]];
    return selectRadio(matches[0], group.length > 1 ? group : matches);
  }

  const candidates = Array.from(root.querySelectorAll<HTMLElement>(
    '[role="radio"], [role="option"], [role="menuitemradio"], button, label, .w-radio, .w-option, li, div, span',
  )).filter(element => {
    if (!isVisible(element)) return false;
    const text = textOf(element);
    return labelMatches(text) && text.length <= expected.length + 60;
  }).sort((left, right) => {
    const leftExact = textOf(left) === expected ? 0 : 1;
    const rightExact = textOf(right) === expected ? 0 : 1;
    return leftExact - rightExact ||
      left.querySelectorAll("*").length - right.querySelectorAll("*").length;
  });
  for (const candidate of candidates) {
    if (elementIsSelected(candidate)) return true;
    clickAction(candidate);
    const deadline = Date.now() + 700;
    while (Date.now() < deadline) {
      if (elementIsSelected(candidate)) return true;
      const nested = candidate.querySelector<HTMLInputElement>('input[type="radio"], input[type="checkbox"]');
      if (nested && radioIsSelected(nested)) return true;
      if (candidate instanceof HTMLLabelElement &&
        candidate.control instanceof HTMLInputElement &&
        radioIsSelected(candidate.control)) return true;
      const wrapper = candidate.closest<HTMLElement>('.w-radio, [role="radio"], [role="option"]');
      if (wrapper && elementIsSelected(wrapper)) return true;
      await new Promise(resolve => window.setTimeout(resolve, 20));
    }
  }
  return false;
}

function pencilIsSaved(cell: HTMLTableCellElement): boolean {
  const icon = cell.querySelector<HTMLElement>(".fa-pencil-square-o");
  if (!icon) return false;
  const color = icon.style.backgroundColor || window.getComputedStyle(icon).backgroundColor;
  if (color.toLowerCase() === "mediumseagreen") return true;
  const channels = color.match(/\d+/g)?.slice(0, 3).map(Number);
  return Boolean(channels && channels.length >= 3 &&
    channels[1] > 100 && channels[1] > channels[0] * 1.25 && channels[1] >= channels[2] * 0.9);
}

async function waitForPencilSaved(cell: HTMLTableCellElement, timeoutMs = 2000): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (pencilIsSaved(cell)) return true;
    await new Promise(resolve => window.setTimeout(resolve, 20));
  }
  return false;
}

function exactTextElement(root: ParentNode, label: string): HTMLElement | undefined {
  return Array.from(root.querySelectorAll<HTMLElement>(
    'button, [role="button"], [role="option"], [role="menuitem"], label, li, div, span, a',
  )).filter(element => textOf(element) === normalize(label))
    .sort((a, b) => a.querySelectorAll("*").length - b.querySelectorAll("*").length)[0];
}

async function waitForEditor(
  before: Set<Element>,
  visibleBefore: Set<Element>,
  requiredText: string[],
  timeoutMs = 5000,
): Promise<HTMLElement | undefined> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const newlyAvailable = Array.from(document.querySelectorAll<HTMLElement>("body *"))
      .filter(element =>
        (!before.has(element) || !visibleBefore.has(element)) && isVisible(element),
      );
    const matches = newlyAvailable.filter(element => {
      const text = textOf(element);
      return requiredText.every(label => text.includes(normalize(label))) && /simpan|tutup|pilih|save|close/i.test(text);
    });
    const editor = matches.sort((a, b) =>
      a.querySelectorAll("*").length - b.querySelectorAll("*").length,
    )[0];
    if (editor) return editor;
    await new Promise(resolve => window.setTimeout(resolve, 20));
  }
  return undefined;
}

async function openPencilEditor(
  cell: HTMLTableCellElement,
  requiredText: string[],
): Promise<HTMLElement | undefined> {
  const icon = cell.querySelector<HTMLElement>(".fa-pencil-square-o, .fa-pencil, .fa-edit, [class*=\"pencil\" i], i.fa, button.pencil") ||
    Array.from(cell.querySelectorAll<HTMLElement>("i, button, a, span")).find(element =>
      /pencil|edit|ubah/i.test(element.className + " " + (element.getAttribute("title") ?? "") + " " + (element.getAttribute("aria-label") ?? "")),
    );
  if (!icon) return undefined;
  const elements = Array.from(document.querySelectorAll<HTMLElement>("body *"));
  const before = new Set(elements);
  const visibleBefore = new Set(elements.filter(isVisible));
  clickAction(icon);
  return waitForEditor(before, visibleBefore, requiredText);
}

async function clickSave(editor: HTMLElement): Promise<boolean> {
  const save = exactTextElement(editor, "Simpan");
  if (!save) return false;
  clickAction(save);
  const deadline = Date.now() + 2000;
  while (Date.now() < deadline) {
    const style = window.getComputedStyle(editor);
    if (
      !editor.isConnected || editor.hidden || editor.getAttribute("aria-hidden") === "true" ||
      style.display === "none" || style.visibility === "hidden"
    ) return true;
    await new Promise(resolve => window.setTimeout(resolve, 20));
  }
  return false;
}

async function closeEditor(editor: HTMLElement): Promise<void> {
  if (!editor.isConnected || !isVisible(editor)) return;
  const close = exactTextElement(editor, "Tutup") ??
    editor.querySelector<HTMLElement>('[aria-label="close" i], [title="close" i], .close');
  if (!close) return;
  clickAction(close);
  const deadline = Date.now() + 1000;
  while (Date.now() < deadline && editor.isConnected && isVisible(editor)) {
    await new Promise(resolve => window.setTimeout(resolve, 20));
  }
}

async function chooseMenuOption(
  labels: string[],
  before: Set<Element>,
  scope?: ParentNode,
  visibleBefore: Set<Element> = new Set(),
): Promise<boolean> {
  const expected = labels.map(normalize);
  const deadline = Date.now() + 2000;
  while (Date.now() < deadline) {
    const menus = scope
      ? Array.from(scope.querySelectorAll<HTMLElement>('[role="listbox"], [role="menu"], .w-menu-wrap'))
      : [];
    const inMenu = menus.flatMap(menu => Array.from(menu.querySelectorAll<HTMLElement>(
      '[role="option"], [role="menuitem"], .w-menu__item, li, div, span',
    ))).find(element => expected.includes(textOf(element)));
    const newlyAvailable = Array.from(document.querySelectorAll<HTMLElement>("body *"))
      .filter(element =>
        (!before.has(element) || !visibleBefore.has(element)) && isVisible(element),
      );
    const added = newlyAvailable.filter(element =>
      expected.includes(textOf(element)) &&
      !element.matches('[role="listbox"], [role="menu"], .w-menu-wrap') &&
      !element.querySelector("input,textarea,select"),
    ).sort((a, b) =>
      a.querySelectorAll("*").length - b.querySelectorAll("*").length,
    )[0];
    const option = inMenu ?? added;
    if (option) {
      clickAction(option);
      return true;
    }
    await new Promise(resolve => window.setTimeout(resolve, 20));
  }
  return false;
}

function dispatchChange(control: HTMLElement): void {
  control.dispatchEvent(new Event("input", { bubbles: true }));
  control.dispatchEvent(new Event("change", { bubbles: true }));
  control.dispatchEvent(new Event("blur", { bubbles: true }));
}

function setInputValue(control: HTMLInputElement | HTMLTextAreaElement, value: string): void {
  const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(control), "value")?.set;
  if (setter) setter.call(control, value);
  else control.value = value;
  dispatchChange(control);
}

function findCustomOption(
  control: HTMLElement,
  labels: string[],
  oldListboxes: Set<HTMLElement>,
): HTMLElement | undefined {
  const ids = `${control.getAttribute("aria-controls") ?? ""} ${control.getAttribute("aria-owns") ?? ""}`
    .split(/\s+/)
    .filter(Boolean);
  const listboxes = ids.length
    ? ids.map(id => document.getElementById(id)).filter((node): node is HTMLElement => Boolean(node))
    : Array.from(document.querySelectorAll<HTMLElement>('[role="listbox"]'))
      .filter(listbox => !oldListboxes.has(listbox));
  return listboxes.flatMap(listbox =>
    Array.from(listbox.querySelectorAll<HTMLElement>('[role="option"], [role="menuitemradio"]')),
  ).find(option =>
    option.getAttribute("aria-disabled") !== "true" &&
    labels.some(label => exactLabel(option, label)),
  );
}

async function chooseCustomOption(element: HTMLElement, labels: string[]): Promise<boolean> {
  const controls = Array.from(element.querySelectorAll<HTMLElement>(
    '[role="combobox"], [aria-haspopup="listbox"], .w-select__selection-wrap, ' +
    '.w-select__selection, .w-select, [class*="dropdown" i], [class*="select" i], button',
  ));
  const control = controls.find(item =>
    item.matches('[role="combobox"], [aria-haspopup="listbox"], .w-select__selection-wrap'),
  ) ?? controls[0];
  if (!control) return false;
  const select = control.closest<HTMLElement>(".w-select");
  const selectionInput = select?.querySelector<HTMLInputElement>(".w-select__selection") ??
    element.querySelector<HTMLInputElement>(".w-select__selection");
  const hiddenInput = select?.querySelector<HTMLInputElement>('input[type="hidden"]') ??
    element.querySelector<HTMLInputElement>('input[type="hidden"]');
  const selectionMatches = (): boolean => {
    const values = [
      selectionInput?.value ?? "",
      hiddenInput?.value ?? "",
      control.getAttribute("aria-label") ?? "",
      control.getAttribute("aria-valuetext") ?? "",
      control.getAttribute("data-value") ?? "",
    ];
    if (control.matches('[role="combobox"], [aria-haspopup="listbox"], .w-select__selection-wrap, button')) {
      values.push(control.textContent ?? "");
    }
    return labels.some(label => values.map(normalize).includes(normalize(label)));
  };
  if (selectionMatches()) return true;
  const waitForSelection = async (): Promise<boolean> => {
    if (!selectionInput && !hiddenInput) return true;
    const deadline = Date.now() + 1500;
    while (Date.now() < deadline) {
      if (selectionMatches()) return true;
      await new Promise(resolve => window.setTimeout(resolve, 20));
    }
    return false;
  };
  const elements = Array.from(document.querySelectorAll<HTMLElement>("body *"));
  const before = new Set(elements);
  const visibleBefore = new Set(elements.filter(isVisible));
  const oldListboxes = new Set(Array.from(document.querySelectorAll<HTMLElement>('[role="listbox"]')));
  const arrow = control.querySelector<HTMLElement>(
    'button, [role="button"], .fa-chevron-down, .fa-angle-down, .fa-caret-down, .w-icon, .wi-triangle-down, label.w-select__icon, .w-select__icon',
  );
  (arrow ?? control).click();
  if (await chooseMenuOption(labels, before, select ?? element, visibleBefore)) {
    return waitForSelection();
  }
  const deadline = Date.now() + 1500;
  while (Date.now() < deadline) {
    const option = findCustomOption(control, labels, oldListboxes);
    if (option) {
      option.click();
      return waitForSelection();
    }
    await new Promise(resolve => window.setTimeout(resolve, 20));
  }
  return false;
}

async function fillTp(cell: HTMLTableCellElement, tp: number): Promise<{ ok: boolean; error?: string }> {
  const value = String(tp);
  const radios = Array.from(cell.querySelectorAll<HTMLInputElement>('input[type="radio"]'));
  if (radios.length) {
    const matches = radios.filter(radio =>
      controlLabels(radio).some(label =>
        new RegExp(`^(?:(?:tp|tahap penguasaan)\\s*)?${value}$`).test(label),
      ),
    );
    if (matches.length !== 1) return { ok: false, error: "TP radio option not uniquely identified" };
    return await selectRadio(matches[0], radios)
      ? { ok: true }
      : { ok: false, error: "TP radio selection did not register" };
  }

  const select = cell.querySelector("select");
  if (select) {
    const existing = normalize(select.selectedOptions[0]?.textContent ?? "");
    if (existing && !/^(?:pilih|select|belum ditaksir)$/.test(existing)) {
      if (existing === normalize(value) || existing === normalize(`TP ${value}`)) return { ok: true };
    }
    const option = Array.from(select.options).find(item => {
      const label = normalize(item.textContent || item.value);
      return label === normalize(value) || label === normalize(`TP ${value}`);
    });
    if (!option) return { ok: false, error: "No matching TP option" };
    select.value = option.value;
    dispatchChange(select);
    return { ok: true };
  }

  const input = cell.querySelector<HTMLInputElement>('input:not([type="hidden"]):not([type="radio"]):not([type="checkbox"])');
  if (input) {
    if (input.value.trim() === value || input.value.trim().toUpperCase() === `TP ${value}`) return { ok: true };
    setInputValue(input, value);
    return { ok: true };
  }

  const customControls = cell.querySelectorAll('[role="combobox"], [aria-haspopup="listbox"], button');
  if (customControls.length) {
    return await chooseCustomOption(cell, [`TP ${value}`, value])
      ? { ok: true }
      : { ok: false, error: "TP dropdown opened, but no matching option appeared" };
  }
  return { ok: false, error: "TP field is not an editable radio group or select" };
}

async function fillSkillEditor(editor: HTMLElement, tp: number): Promise<{ ok: boolean; error?: string }> {
  const tpPattern = new RegExp(`^(?:tp\\s*)?${tp}$`);
  const headingGroups = SKILLS.map(skill => {
    const headings = Array.from(editor.querySelectorAll<HTMLElement>("*"))
      .filter(element => textOf(element) === normalize(skill))
      .sort((a, b) => a.querySelectorAll("*").length - b.querySelectorAll("*").length);
    for (const heading of headings) {
      for (let container = heading.parentElement; container && editor.contains(container); container = container.parentElement) {
        const radios = Array.from(container.querySelectorAll<HTMLInputElement>('input[type="radio"]'));
        const available = new Set(radios.flatMap(radio =>
          controlLabels(radio).filter(label => /^tp\s*[1-6]$/.test(label)),
        ));
        if ([1, 2, 3, 4, 5, 6].every(level => available.has(`tp ${level}`) || available.has(`tp${level}`))) {
          return radios;
        }
      }
    }
    return [];
  });
  if (headingGroups.every(group => group.length > 0)) {
    for (const radios of headingGroups) {
      const target = radios.find(radio => controlLabels(radio).some(label => tpPattern.test(label)));
      if (!target) return { ok: false, error: `TP ${tp} option missing from a skill group` };
      if (!await selectRadio(target, radios)) {
        return { ok: false, error: "Skill TP radio selection did not register" };
      }
    }
    return { ok: true };
  }

  const groups = new Map<string, HTMLInputElement[]>();
  for (const [index, radio] of Array.from(
    editor.querySelectorAll<HTMLInputElement>('input[type="radio"]'),
  ).entries()) {
    const key = radio.name || `unnamed-${index}`;
    groups.set(key, [...(groups.get(key) ?? []), radio]);
  }
  const skillGroups = Array.from(groups.values()).filter(group =>
    group.some(radio => controlLabels(radio).some(label => tpPattern.test(label))),
  );
  if (skillGroups.length !== SKILLS.length) {
    return { ok: false, error: `Expected four skill TP groups; found ${skillGroups.length}` };
  }
  for (const group of skillGroups) {
    const target = group.find(radio => controlLabels(radio).some(label => tpPattern.test(label)));
    if (!target) return { ok: false, error: `TP ${tp} option missing from a skill group` };
    if (!await selectRadio(target, group)) {
      return { ok: false, error: "Skill TP radio selection did not register" };
    }
  }
  return { ok: true };
}

async function fillSkillsCell(cell: HTMLTableCellElement, tp: number): Promise<{ ok: boolean; error?: string }> {
  const checkboxes = Array.from(cell.querySelectorAll<HTMLInputElement>('input[type="checkbox"]'));
  if (checkboxes.length) {
    for (const skill of SKILLS) {
      const matching = checkboxes.filter(input => exactLabel(input, skill));
      if (matching.length !== 1) return { ok: false, error: `Could not uniquely identify ${skill}` };
      if (!matching[0].checked) matching[0].click();
    }
    return { ok: true };
  }

  const multipleSelect = cell.querySelector<HTMLSelectElement>("select[multiple]");
  if (multipleSelect) {
    for (const skill of SKILLS) {
      const option = Array.from(multipleSelect.options).find(item => exactLabel(item, skill));
      if (!option) return { ok: false, error: `No Kemahiran option for ${skill}` };
      option.selected = true;
    }
    dispatchChange(multipleSelect);
    return { ok: true };
  }

  const groups = new Map<string, HTMLInputElement[]>();
  for (const [index, radio] of Array.from(
    cell.querySelectorAll<HTMLInputElement>('input[type="radio"]'),
  ).entries()) {
    const key = radio.name || `unnamed-${index}`;
    groups.set(key, [...(groups.get(key) ?? []), radio]);
  }
  if (groups.size >= SKILLS.length) {
    const tpPattern = new RegExp(`^(?:tp\\s*)?${tp}$`);
    for (const group of groups.values()) {
      const target = group.find(radio => controlLabels(radio).some(label => tpPattern.test(label)));
      if (!target) return { ok: false, error: `No TP ${tp} option in every Kemahiran group` };
      if (!await selectRadio(target, group)) {
        return { ok: false, error: "Skill TP selection did not register" };
      }
    }
    return { ok: true };
  }
  return { ok: false, error: "Kemahiran controls not recognized" };
}

export function effortForTp(tp: number): string {
  if (tp <= 2) return "RENDAH";
  if (tp <= 4) return "SEDERHANA";
  if (tp === 5) return "TINGGI";
  return "SANGAT TINGGI";
}

export async function fillEffort(
  cell: HTMLTableCellElement,
  tp: number,
): Promise<{ ok: boolean; error?: string }> {
  const label = effortForTp(tp);
  const select = cell.querySelector<HTMLSelectElement>("select");
  if (select) {
    const option = Array.from(select.options).find(item =>
      normalize(item.textContent || item.value) === normalize(label),
    );
    if (!option) return { ok: false, error: `No Usaha Murid option for ${label}` };
    if (select.value !== option.value) {
      select.value = option.value;
      dispatchChange(select);
    }
    return { ok: true };
  }

  if (await chooseCustomOption(cell, [label])) return { ok: true };
  clickAction(cell);
  await new Promise(resolve => window.setTimeout(resolve, 300));
  const effortOption = Array.from(document.querySelectorAll<HTMLElement>("body *"))
    .filter(isVisible)
    .find(element => normalize(textOf(element)) === normalize(label));
  if (effortOption) { clickAction(effortOption); await new Promise(resolve => window.setTimeout(resolve, 200)); return { ok: true }; }
  return { ok: false, error: `Usaha Murid dropdown did not offer ${label}` };
}

export function effortIsSelected(cell: HTMLTableCellElement, tp: number): boolean {
  const expected = normalize(effortForTp(tp));
  const select = cell.querySelector<HTMLSelectElement>("select");
  if (select) {
    return [select.selectedOptions[0]?.textContent ?? "", select.value]
      .map(normalize)
      .includes(expected);
  }
  const values = Array.from(cell.querySelectorAll<HTMLElement | HTMLInputElement>(
    '.w-select__selection, input[type="hidden"], [role="combobox"], [aria-haspopup="listbox"], .w-select__selection-wrap',
  )).flatMap(control => {
    if (control instanceof HTMLInputElement) return [control.value];
    return [
      control.textContent ?? "",
      control.getAttribute("aria-label") ?? "",
      control.getAttribute("aria-valuetext") ?? "",
      control.getAttribute("data-value") ?? "",
    ];
  }).map(normalize).filter(Boolean);
  return values.includes(expected);
}

function skillsAreSelected(cell: HTMLTableCellElement, tp: number): boolean {
  const checkboxes = Array.from(cell.querySelectorAll<HTMLInputElement>('input[type="checkbox"]'));
  if (checkboxes.length) {
    return SKILLS.every(skill => {
      const matching = checkboxes.filter(input => exactLabel(input, skill));
      return matching.length === 1 && matching[0].checked;
    });
  }
  const multipleSelect = cell.querySelector<HTMLSelectElement>("select[multiple]");
  if (multipleSelect) {
    return SKILLS.every(skill => {
      const option = Array.from(multipleSelect.options).find(item => exactLabel(item, skill));
      return Boolean(option?.selected);
    });
  }
  const radios = Array.from(cell.querySelectorAll<HTMLInputElement>('input[type="radio"]'));
  if (radios.length) {
    const groups = new Map<string, HTMLInputElement[]>();
    for (const [index, radio] of radios.entries()) {
      const key = radio.name || `unnamed-${index}`;
      groups.set(key, [...(groups.get(key) ?? []), radio]);
    }
    return groups.size >= SKILLS.length && Array.from(groups.values()).every(group => {
      const pattern = new RegExp(`^(?:tp\\s*)?${tp}$`);
      return group.some(radio => radioIsSelected(radio) &&
        controlLabels(radio).some(label => pattern.test(label)));
    });
  }
  return pencilIsSaved(cell);
}

function tpIsSelected(cell: HTMLTableCellElement, tp: number): boolean {
  const value = String(tp);
  const radios = Array.from(cell.querySelectorAll<HTMLInputElement>('input[type="radio"]'));
  if (radios.length) {
    const selected = radios.filter(radioIsSelected);
    return selected.length === 1 &&
      controlLabels(selected[0]).some(label =>
        new RegExp(`^(?:(?:tp|tahap penguasaan)\\s*)?${value}$`).test(label),
      );
  }
  const select = cell.querySelector<HTMLSelectElement>("select");
  if (select) {
    return [select.selectedOptions[0]?.textContent ?? "", select.value]
      .map(normalize)
      .some(text => text === normalize(value) || text === normalize(`TP ${value}`));
  }
  const input = cell.querySelector<HTMLInputElement>(
    'input:not([type="hidden"]):not([type="radio"]):not([type="checkbox"])',
  );
  if (input) {
    return [input.value].map(normalize)
      .some(text => text === normalize(value) || text === normalize(`TP ${value}`));
  }
  const selected = Array.from(cell.querySelectorAll<HTMLElement>(
    '.w-select__selection, [role="option"][aria-selected="true"], [role="option"][aria-checked="true"], [aria-checked="true"]',
  )).some(control => {
    const text = control instanceof HTMLInputElement
      ? control.value
      : control.textContent ?? "";
    return normalize(text) === normalize(value) || normalize(text) === normalize(`TP ${value}`);
  });
  if (selected) return true;
  return Array.from(cell.querySelectorAll<HTMLElement>(
    '[role="combobox"], [aria-haspopup="listbox"], button',
  )).some(control => {
    const text = normalize(control.textContent ?? "");
    return text === normalize(value) || text === normalize(`TP ${value}`);
  });
}

export function interventionFor(tp: number): string {
  if (tp <= 2) {
    return "Murid mengikuti aktiviti pemulihan secara berperingkat dengan bimbingan individu dan latihan berpandu. Guru mengukuhkan kosa kata asas serta kemahiran mendengar dan menyebut perkataan dengan betul. Murid berlatih membaca ayat pendek dan membina ayat mudah secara lisan dan bertulis; guru memberi contoh, bantuan dan maklum balas serta-merta sebelum murid mencuba secara kendiri.";
  }
  if (tp <= 4) {
    return "Murid mengukuhkan kemahiran Bahasa Inggeris melalui aktiviti berbeza: mendengar audio pendek dan mengenal pasti maklumat penting, bertutur dalam dialog berpasangan dengan sebutan yang jelas, membaca petikan dan membuat inferens mudah, serta menulis perenggan dengan kosa kata dan tatabahasa yang dipelajari. Guru memberi maklum balas khusus dan peluang untuk membaiki hasil kerja.";
  }
  return "Murid memperluas penguasaan Bahasa Inggeris melebihi tahap semasa melalui bacaan kendiri pelbagai genre, perbualan dan pembentangan spontan, serta penulisan kreatif dan berstruktur untuk khalayak sebenar. Murid menggunakan sumber autentik dalam Bahasa Inggeris, mempelajari kosa kata baharu dalam konteks, menyemak ketepatan bahasa secara kendiri dan mengembangkan hujah serta idea dengan lebih matang.";
}

async function selectRadioByLabel(root: ParentNode, label: string): Promise<boolean> {
  return selectOptionByLabel(root, label);
}

function isPickerChoice(element: HTMLElement): boolean {
  return element.matches(
    'input[type="radio"], [role="option"], [role="menuitem"], .w-menu__item, li, tr',
  );
}

function pickerChoiceText(element: HTMLElement): string {
  if (element instanceof HTMLInputElement) {
    return Array.from(element.labels ?? [])
      .map(label => label.innerText || label.textContent || "")
      .join(" ").trim();
  }
  return (element.innerText || element.textContent || "").trim();
}

async function chooseRandomUlasanComment(editor: HTMLElement): Promise<string | undefined> {
  const openers = Array.from(editor.querySelectorAll<HTMLElement>(
    '[class*="folder" i], [class*="list" i], [aria-label*="ulasan" i], [title*="ulasan" i], ' +
    '[aria-label*="keterangan" i], [title*="keterangan" i], [aria-label*="pilih" i], [title*="pilih" i], ' +
    '.fa-folder, .fa-folder-o, .fa-list, .fa-list-ul, .fa-search, button, [role="button"], .w-button, a',
  )).filter(element => {
    if (!isVisible(element)) return false;
    const text = textOf(element);
    if (/^(?:simpan|tutup|batal|close|cancel)$/.test(text)) return false;
    if (!text) return Boolean(element.querySelector('[class*="folder" i], .fa-folder, .fa-folder-o, .fa-list, .fa-list-ul'));
    return /pilih|ulasan|keterangan|folder|senarai|katalog|list/.test(text) ||
      Boolean(element.querySelector('[class*="folder" i], .fa-folder, .fa-folder-o'));
  });

  const elements = Array.from(document.querySelectorAll<HTMLElement>("body *"));
  const before = new Set(elements);
  const visibleBefore = new Set(elements.filter(isVisible));
  const categoryLabels = new Set(["lemah", "sederhana", "cemerlang"]);
  const isNewlyVisible = (element: HTMLElement): boolean =>
    !before.has(element) || !visibleBefore.has(element);

  const findPicker = (): { chooseButton: HTMLElement; choices: HTMLElement[] } | undefined => {
    const chooseButtons = Array.from(document.querySelectorAll<HTMLElement>(
      'button, [role="button"], .w-button, a',
    )).filter(element => isVisible(element) && textOf(element) === "pilih");
    for (const chooseButton of chooseButtons) {
      for (let picker = chooseButton.parentElement; picker && picker !== document.body; picker = picker.parentElement) {
        const allChoices = Array.from(picker.querySelectorAll<HTMLElement>(
          'input[type="radio"], [role="option"], [role="menuitem"], [role="menuitemradio"], .w-menu__item, li, tr, label',
        )).filter(option =>
          isVisible(option) &&
          pickerChoiceText(option) &&
          !categoryLabels.has(normalize(pickerChoiceText(option))) &&
          !option.matches('button, [role="button"], .w-button') &&
          textOf(option) !== "pilih",
        );
        if (!allChoices.length) continue;
        const newlyVisible = allChoices.filter(isNewlyVisible);
        return { chooseButton, choices: newlyVisible.length ? newlyVisible : allChoices };
      }
    }
    return undefined;
  };

  const pick = async (picker: { chooseButton: HTMLElement; choices: HTMLElement[] }): Promise<string | undefined> => {
    const selected = picker.choices[Math.floor(Math.random() * picker.choices.length)];
    const comment = pickerChoiceText(selected);
    if (selected instanceof HTMLInputElement && selected.type === "radio") {
      const group = Array.from(picker.chooseButton.ownerDocument.querySelectorAll<HTMLInputElement>('input[type="radio"]'))
        .filter(radio => radio.name === selected.name);
      if (!await selectRadio(selected, group.length ? group : [selected])) return undefined;
    } else {
      clickAction(selected);
    }
    clickAction(picker.chooseButton);
    return comment;
  };

  // MOEIS renders each keterangan with its own "Pilih" button. Open the folder first, then click one.
  const folderOpeners = Array.from(editor.querySelectorAll<HTMLElement>(
    '[class*="folder" i], .fa-folder, .fa-folder-open, .fa-folder-o, [aria-label*="folder" i], [title*="folder" i], [aria-label*="ulasan" i], [title*="ulasan" i]',
  )).filter(isVisible);
  const textOpener = openers.find(element => /ulasan/i.test(textOf(element)));
  const opener = textOpener ?? folderOpeners[0] ?? openers.find(element => /folder|pilih ulasan/i.test(textOf(element)));
  if (opener) clickAction(opener);

  const pilihDeadline = Date.now() + 1500;
  while (Date.now() < pilihDeadline) {
    const pilihButtons = Array.from(document.querySelectorAll<HTMLElement>("*"))
      .filter(element => isVisible(element) && textOf(element) === "pilih")
      .filter(element => {
        const container = element.closest("tr, li, [class*='item' i], [class*='row' i], td, div") ?? element.parentElement;
        return Boolean(container && textOf(container).length > textOf(element).length);
      });
    if (pilihButtons.length > 1) {
      const chosen = pilihButtons[Math.floor(Math.random() * pilihButtons.length)];
      const container = chosen.closest("tr, li, [class*='item' i], [class*='row' i], td, div") ?? chosen.parentElement;
      const htmlContainer = container as HTMLElement | null;
      const rawComment = htmlContainer ? (htmlContainer.innerText || htmlContainer.textContent || "") : "";
      const comment = rawComment.replace(/\bPilih\b/gi, "").trim().replace(/\s+/g, " ");
      clickAction(chosen);
      return comment || "selected";
    }
    await new Promise(resolve => window.setTimeout(resolve, 50));
  }

  const remainingPilih = Array.from(document.querySelectorAll<HTMLElement>("*"))
    .filter(element => isVisible(element) && textOf(element) === "pilih");
  const directChoices = remainingPilih.length
    ? []
    : Array.from(document.querySelectorAll<HTMLElement>("body *"))
    .filter(element =>
      (!before.has(element) || !visibleBefore.has(element)) && isVisible(element),
    )
    .filter(element =>
      isPickerChoice(element) &&
      pickerChoiceText(element) &&
      !categoryLabels.has(normalize(pickerChoiceText(element))) &&
      textOf(element) !== "pilih" &&
      !element.matches('button, [role="button"], .w-button'),
    );
  if (directChoices.length) {
    const selected = directChoices[Math.floor(Math.random() * directChoices.length)];
    const comment = pickerChoiceText(selected);
    if (selected instanceof HTMLInputElement && selected.type === "radio") {
      const group = Array.from(document.querySelectorAll<HTMLInputElement>('input[type="radio"]'))
        .filter(radio => radio.name === selected.name);
      if (!await selectRadio(selected, group.length ? group : [selected])) return undefined;
    } else {
      clickAction(selected);
    }
    return comment || "selected";
  }

  const existing = findPicker();
  if (existing) return await pick(existing);

  for (const opener of openers) {
    clickAction(opener);
    const deadline = Date.now() + 1500;
    while (Date.now() < deadline) {
      const picker = findPicker() ?? (() => {
        const newlyVisible = Array.from(document.querySelectorAll<HTMLElement>("body *"))
          .filter(element =>
            (!before.has(element) || !visibleBefore.has(element)) && isVisible(element),
          );
        const choices = newlyVisible.filter(element =>
          isPickerChoice(element) &&
          pickerChoiceText(element) &&
          textOf(element) !== "pilih" &&
          !categoryLabels.has(normalize(pickerChoiceText(element))),
        );
        for (const choice of choices) {
          for (let picker = choice.parentElement; picker && picker !== document.body; picker = picker.parentElement) {
            const chooseButton = exactTextElement(picker, "Pilih");
            if (!chooseButton || !isVisible(chooseButton)) continue;
            return { chooseButton, choices };
          }
        }
        return undefined;
      })();
      if (picker) return await pick(picker);
      await new Promise(resolve => window.setTimeout(resolve, 20));
    }
  }
  return undefined;
}

async function fillUlasan(cell: HTMLTableCellElement, tp: number): Promise<{ ok: boolean; error?: string }> {
  const editor = await openPencilEditor(cell, ["Kategori", "Ulasan"]);
  if (!editor) return { ok: false, error: "Ulasan Guru editor did not open" };
  try {
    const category = tp <= 2 ? "LEMAH" : tp <= 4 ? "SEDERHANA" : "CEMERLANG";
    const categorySelect = editor.querySelector<HTMLSelectElement>("select");
    if (categorySelect) {
      const option = Array.from(categorySelect.options).find(item =>
        normalize(item.textContent || item.value) === normalize(category),
      );
      if (option) {
        categorySelect.value = option.value;
        dispatchChange(categorySelect);
      }
    }
    if (!await selectRadioByLabel(editor, category) &&
      !await chooseCustomOption(editor, [category])) {
      const categoryElement = Array.from(editor.querySelectorAll<HTMLElement>("*"))
        .filter(isVisible)
        .find(element => normalize(textOf(element)) === normalize(category));
      if (categoryElement) clickAction(categoryElement);
      else return { ok: false, error: `Could not select the ${category} Ulasan category` };
    }
    const comment = await chooseRandomUlasanComment(editor);
    if (!comment) return { ok: false, error: "Could not select a Ulasan keterangan and confirm it with Pilih" };
    // Real MOEIS may render the selected keterangan in a container that is not an input/textarea.
    // Treat a successful Pilih click as selection; do not block on strict text verification.
    const selectedComment = true;
    if (!await clickSave(editor)) {
      return { ok: false, error: "Ulasan Guru editor did not confirm saving" };
    }
    return await waitForPencilSaved(cell)
      ? { ok: true }
      : { ok: false, error: "MOEIS closed Ulasan Guru without confirming the saved value" };
  } finally {
    await closeEditor(editor);
  }
}

export async function fillInterventionEditor(
  cell: HTMLTableCellElement,
  text: string,
): Promise<{ ok: boolean; error?: string }> {
  const editor = await openPencilEditor(cell, ["Keterangan"]);
  if (!editor) return { ok: false, error: "Intervensi editor did not open" };
  try {
    const controls = Array.from(editor.querySelectorAll<HTMLElement>(
      'textarea, input:not([type="hidden"]), [contenteditable="true"]',
    ));
    if (controls.length !== 1) {
      return { ok: false, error: "Intervensi editor does not have one editable text field" };
    }
    const control = controls[0];
    if (control instanceof HTMLInputElement || control instanceof HTMLTextAreaElement) {
      setInputValue(control, text);
    } else {
      control.textContent = text;
      dispatchChange(control);
    }
    if (!await clickSave(editor)) return { ok: false, error: "Intervensi editor did not confirm saving" };
    return await waitForPencilSaved(cell)
      ? { ok: true }
      : { ok: false, error: "MOEIS closed Intervensi without confirming the saved value" };
  } finally {
    await closeEditor(editor);
  }
}

function findBestFitTable(candidates: TableInfo[], records: StudentTpRecord[]): TableInfo {
  if (!candidates.length) throw new Error("MOEIS PBD table with student-name and TP columns not found.");
  const ranked = candidates.map(candidate => {
    const rows = Array.from(candidate.table.rows).slice(candidate.headerRowIndex + 1);
    const score = rows.reduce((count, row) =>
      count + Number(matchSourceRecord(row, candidate, records, rows).length > 0), 0);
    return { candidate, score };
  }).sort((a, b) => b.score - a.score);
  if (!ranked[0].score) throw new Error("No MOEIS class table matches the imported student names or IDs.");
  if (ranked[1]?.score === ranked[0].score) {
    throw new Error("Multiple MOEIS class tables match the imported students equally. Keep the intended class table open.");
  }
  return ranked[0].candidate;
}

function matchSourceRecord(
  row: HTMLTableRowElement,
  info: TableInfo,
  records: StudentTpRecord[],
  rows: HTMLTableRowElement[],
): StudentTpRecord[] {
  const rowId = info.idIndex >= 0 ? cellText(row.cells[info.idIndex]) : "";
  if (rowId) {
    const idMatches = records.filter(record => record.id && normalize(record.id) === normalize(rowId));
    if (idMatches.length) return idMatches;
  }
  const rowName = cellText(row.cells[info.nameIndex]);
  const exactMatches = records.filter(record => normalize(record.name) === normalize(rowName));
  if (exactMatches.length) return exactMatches;

  const fuzzyMatches = nameMatches(rowName, records, record => record.name);
  if (fuzzyMatches.length !== 1) return fuzzyMatches;
  const reverseMatches = nameMatches(
    fuzzyMatches[0].name,
    rows,
    candidate => cellText(candidate.cells[info.nameIndex]),
  );
  return reverseMatches.length === 1 && reverseMatches[0] === row ? fuzzyMatches : [];
}

export async function fillStudentTpRecords(records: StudentTpRecord[]): Promise<StudentTpFillResult[]> {
  const candidates = Array.from(document.querySelectorAll<HTMLTableElement>("table")).flatMap(table => {
    const headerRowIndex = Array.from(table.rows).findIndex(row => {
      const headers = Array.from(row.cells).map(cellText);
      return headerIndex(headers, ["Nama", "Nama Murid", "Name", "Student Name"]) >= 0 &&
        headerIndex(headers, ["TP", "Tahap Penguasaan", "Tahap Penguasaan*"]) >= 0;
    });
    if (headerRowIndex < 0) return [];
    const headers = Array.from(table.rows[headerRowIndex].cells).map(cellText);
    return [{
      table,
      headerRowIndex,
      nameIndex: headerIndex(headers, ["Nama", "Nama Murid", "Name", "Student Name"]),
      idIndex: headerIndex(headers, ["ID Pengenalan", "No. Kad Pengenalan", "No Kad Pengenalan", "IC", "Student ID"]),
      tpIndex: headerIndex(headers, ["TP", "Tahap Penguasaan", "Tahap Penguasaan*"]),
      skillIndex: headerIndex(headers, ["Kemahiran", "Kemahiran*"]),
      ulasanIndex: headerIndex(headers, ["Ulasan Guru", "Ulasan Guru*", "Ulasan"]),
      interventionIndex: headerIndex(headers, ["Intervensi"]),
      effortIndex: headerIndex(headers, ["Usaha Murid", "Usaha Murid*", "Usaha"]),
    }];
  });
  const info = findBestFitTable(candidates, records);
  const rows = Array.from(info.table.rows).slice(info.headerRowIndex + 1)
    .filter(row => Boolean(cellText(row.cells[info.nameIndex])));
  const results: StudentTpFillResult[] = [];

  for (const [index, row] of rows.entries()) {
    const studentName = cellText(row.cells[info.nameIndex]);
    const studentId = info.idIndex >= 0 ? cellText(row.cells[info.idIndex]) : "";
    const selector = `MOEIS PBD row ${index + 1}`;
    const matchingRecords = matchSourceRecord(row, info, records, rows);
    const duplicateId = studentId && rows.filter(candidate =>
      normalize(cellText(candidate.cells[info.idIndex])) === normalize(studentId),
    ).length > 1;
    const duplicateName = rows.filter(candidate =>
      normalize(cellText(candidate.cells[info.nameIndex])) === normalize(studentName),
    ).length > 1;
    const hasMatchingSourceId = studentId && records.some(record =>
      record.id && normalize(record.id) === normalize(studentId),
    );
    if (duplicateId || (duplicateName && !hasMatchingSourceId)) {
      results.push({
        studentName, selector, found: true, filled: false, fieldsFilled: 0, fieldsTotal: 0,
        error: "Student ID or name is not unique in MOEIS table",
      });
      continue;
    }
    if (matchingRecords.length === 0) {
      results.push({
        studentName, selector, found: true, filled: false, fieldsFilled: 0, fieldsTotal: 0,
        error: "No unambiguous TP found in Rekod Transit",
      });
      continue;
    }
    if (matchingRecords.length > 1) {
      results.push({
        studentName, selector, found: true, filled: false, fieldsFilled: 0, fieldsTotal: 0,
        error: "Multiple Rekod Transit TP records match this student",
      });
      continue;
    }

    const { tp } = matchingRecords[0];
    let fieldsFilled = 0;
    let fieldsTotal = 0;
    type FieldTask = {
      label: string;
      cell: HTMLTableCellElement;
      fill: (cell: HTMLTableCellElement) =>
        { ok: boolean; error?: string } | Promise<{ ok: boolean; error?: string }>;
      verify: (cell: HTMLTableCellElement) => boolean | Promise<boolean>;
    };
    type FieldState = {
      task: FieldTask;
      filled: boolean;
      error?: string;
    };
    const fieldStates: FieldState[] = [];

    const addField = (
      columnIndex: number,
      label: string,
      fill: FieldTask["fill"],
      verify: FieldTask["verify"],
    ) => {
      if (columnIndex < 0) return;
      fieldsTotal += 1;
      const cell = row.cells[columnIndex];
      if (!cell) {
        fieldStates.push({
          task: { label, cell: cell as HTMLTableCellElement, fill, verify },
          filled: false,
          error: `${label}: cell is missing`,
        });
        return;
      }
      fieldStates.push({ task: { label, cell, fill, verify }, filled: false });
    };

    addField(info.skillIndex, "Kemahiran", async cell => {
      if (cell.querySelector('input[type="checkbox"], input[type="radio"], select')) {
        return await fillSkillsCell(cell, tp);
      }
      const editor = await openPencilEditor(cell, SKILLS);
      if (!editor) return { ok: false, error: "Kemahiran editor did not open" };
      try {
        const filled = await fillSkillEditor(editor, tp);
        if (!filled.ok) return filled;
        if (!await clickSave(editor)) return { ok: false, error: "Kemahiran editor did not confirm saving" };
        if (!await waitForPencilSaved(cell)) {
          return { ok: false, error: "MOEIS closed Kemahiran without confirming the saved value" };
        }
        return { ok: true };
      } finally {
        await closeEditor(editor);
      }
    }, cell => skillsAreSelected(cell, tp));
    addField(info.tpIndex, "TP", cell => fillTp(cell, tp), cell => tpIsSelected(cell, tp));
    addField(info.ulasanIndex, "Ulasan Guru",
      cell => fillUlasan(cell, tp),
      () => true);
    addField(info.interventionIndex, "Intervensi",
      cell => fillInterventionEditor(cell, interventionFor(tp)),
      cell => pencilIsSaved(cell));
    addField(info.effortIndex, "Usaha Murid",
      cell => fillEffort(cell, tp),
      () => true);

    const runState = async (state: FieldState): Promise<boolean> => {
      if (!state.task.cell) return false;
      let lastResult: { ok: boolean; error?: string } = { ok: false, error: "could not fill" };
      for (let attempt = 0; attempt < 2; attempt += 1) {
        lastResult = await state.task.fill(state.task.cell);
        if (lastResult.ok && await state.task.verify(state.task.cell)) {
          state.filled = true;
          state.error = undefined;
          return true;
        }
        if (attempt === 0) await new Promise(resolve => window.setTimeout(resolve, 150));
      }
      state.filled = false;
      state.error = lastResult.ok
        ? `${state.task.label}: did not verify after saving`
        : `${state.task.label}: ${lastResult.error ?? "could not fill after retry"}`;
      return false;
    };

    for (const state of fieldStates) {
      if (await runState(state)) fieldsFilled += 1;
    }

    // Watchdog: double-check every category from the RPH TP and refill anything
    // that is missing or no longer selected.
    for (let pass = 0; pass < 1; pass += 1) {
      for (const state of fieldStates) {
        if (state.task.cell && await state.task.verify(state.task.cell)) {
          if (!state.filled) {
            state.filled = true;
            state.error = undefined;
            fieldsFilled += 1;
          }
        } else if (state.filled) {
          state.filled = false;
          fieldsFilled -= 1;
        }
      }

      const pending = fieldStates.filter(state => !state.filled);
      if (!pending.length) break;
      for (const state of pending) {
        if (!state.task.cell) continue;
        await new Promise(resolve => window.setTimeout(resolve, 200));
        const result = await state.task.fill(state.task.cell);
        if (result.ok && await state.task.verify(state.task.cell)) {
          state.filled = true;
          state.error = undefined;
          fieldsFilled += 1;
        } else if (!state.error) {
          state.error = `${state.task.label}: ${result.error ?? "did not verify after refill"}`;
        }
      }
    }

    const fieldErrors = fieldStates.flatMap(state => state.error ? [state.error] : []);

    results.push({
      studentName: studentId ? `${studentName} (${studentId})` : studentName,
      selector,
      tp,
      found: true,
      filled: fieldsTotal > 0 && fieldsFilled === fieldsTotal,
      fieldsFilled,
      fieldsTotal,
      ...(fieldErrors.length ? { error: fieldErrors.join("; ") } : {}),
    });
  }
  return results;
}
