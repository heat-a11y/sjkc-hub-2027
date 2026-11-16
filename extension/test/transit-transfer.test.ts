import { beforeEach, describe, expect, it } from "vitest";
import { fillStudentTpRecords } from "../src/moeis-fill";
import { parseTransitTables, readTransitTablesFromPage } from "../src/transit-import";
import type { TransitTableData } from "../../shared/types";
import { findTransferTabs, isMoeisPbdUrl } from "../src/workflow";

describe("Rekod Transit import", () => {
  it("imports all student TP records from the whole weekly view", () => {
    const page = document.implementation.createHTMLDocument();
    page.body.innerHTML = `
      <table>
        <tr><th>#</th><th>Nama</th><th>TP</th><th>Catatan</th></tr>
        <tr><td>1</td><td>STUDENT ALPHA</td><td>3</td><td>Comment is ignored</td></tr>
      </table>
      <table>
        <tr><th>#</th><th>Nama Murid</th><th>Tahap Penguasaan</th><th>Catatan</th></tr>
        <tr><td>2</td><td>STUDENT BETA</td><td>TP 5</td><td>Also ignored</td></tr>
      </table>`;

    const injectedReader = Function(
      "pageDocument",
      "pageUrl",
      `return (${readTransitTablesFromPage.toString()})(pageDocument, pageUrl);`,
    ) as (pageDocument: Document, pageUrl: string) => TransitTableData[];
    const tables = injectedReader(page, "https://erph-pm.vercel.app/rekod-transit");

    expect(parseTransitTables(tables)).toEqual({
      records: [
        { name: "STUDENT ALPHA", tp: 3 },
        { name: "STUDENT BETA", tp: 5 },
      ],
      resolvedConflictCount: 0,
      conflictingStudentCount: 0,
      missingTpCount: 0,
    });
  });

  it("reads only the selected radio value and captures student ID", () => {
    const page = document.implementation.createHTMLDocument();
    page.body.innerHTML = `
      <table>
        <tr><th>Nama</th><th>ID Pengenalan</th><th>Tahap Penguasaan</th></tr>
        <tr><td>STUDENT ALPHA</td><td>ID-A</td><td>
          <label><input type="radio" name="tp" value="1">1</label>
          <label><input type="radio" name="tp" value="on" checked>TP 3</label>
          <label><input type="radio" name="tp" value="6">6</label>
        </td></tr>
      </table>`;

    const tables = readTransitTablesFromPage(page, "https://erph-pm.vercel.app/rekod-transit");
    expect(parseTransitTables(tables).records).toEqual([
      { name: "STUDENT ALPHA", id: "ID-A", tp: 3 },
    ]);
  });

  it("deduplicates repeated weekly records but excludes conflicting TP values", () => {
    expect(parseTransitTables([
      { rows: [["Nama", "TP"], ["STUDENT ALPHA", "3"], ["STUDENT BETA", "4"]] },
      { rows: [["Nama", "TP"], ["STUDENT ALPHA", "3"], ["STUDENT BETA", "5"]] },
    ])).toEqual({
      records: [{ name: "STUDENT ALPHA", tp: 3 }],
      resolvedConflictCount: 0,
      conflictingStudentCount: 1,
      missingTpCount: 0,
    });
  });

  it("chooses the most frequently selected TP across the weekly RPH tables", () => {
    const result = parseTransitTables([
      { rows: [["Nama", "TP"], ["STUDENT ALPHA", "4"], ["STUDENT BETA", "2"]] },
      { rows: [["Nama", "TP"], ["STUDENT ALPHA", "4"], ["STUDENT BETA", "3"]] },
      { rows: [["Nama", "TP"], ["STUDENT ALPHA", "5"], ["STUDENT BETA", "2"]] },
      { rows: [["Nama", "TP"], ["STUDENT ALPHA", "4"], ["STUDENT BETA", "3"]] },
    ]);

    expect(result.records).toEqual([
      { name: "STUDENT ALPHA", tp: 4 },
    ]);
    expect(result.resolvedConflictCount).toBe(1);
    expect(result.conflictingStudentCount).toBe(1);
  });

  it("reports named rows with no selected TP without discarding valid students", () => {
    expect(parseTransitTables([
      { rows: [["Nama", "TP"], ["STUDENT ALPHA", "4"], ["STUDENT BETA", ""]] },
    ])).toEqual({
      records: [{ name: "STUDENT ALPHA", tp: 4 }],
      resolvedConflictCount: 0,
      conflictingStudentCount: 0,
      missingTpCount: 1,
    });
  });

  it("rejects missing tables and invalid TP values", () => {
    expect(() => parseTransitTables([])).toThrow("Rekod Transit table");
    expect(() => parseTransitTables([{ rows: [["Nama", "TP"], ["STUDENT ALPHA", "7"]] }]))
      .toThrow("TP from 1 to 6");
  });
});

describe("MOEIS TP transfer", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("fills only empty TP fields for exact student-name matches", async () => {
    document.body.innerHTML = `
      <table>
        <tr><th>Nama</th><th>Other</th><th>Tahap Penguasaan*</th><th>Teacher comment</th></tr>
        <tr><td>STUDENT ALPHA</td><td><input value="1.1"></td><td><select><option value="">Pilih</option><option value="3">3</option></select></td><td><textarea></textarea></td></tr>
        <tr><td>STUDENT BETA</td><td><input value="1.2"></td><td><select><option value="">Pilih</option><option value="TP 5">TP 5</option></select></td><td><textarea></textarea></td></tr>
      </table>`;

    const results = await fillStudentTpRecords([
      { name: "STUDENT ALPHA", tp: 3 },
      { name: "STUDENT BETA", tp: 5 },
      { name: "STUDENT GAMMA", tp: 2 },
    ]);

    expect(Array.from(document.querySelectorAll("select")).map(control => control.value)).toEqual(["3", "TP 5"]);
    expect(Array.from(document.querySelectorAll("input")).map(control => control.value)).toEqual(["1.1", "1.2"]);
    expect(Array.from(document.querySelectorAll("textarea")).every(control => control.value === "")).toBe(true);
    expect(results.map(result => result.filled)).toEqual([true, true]);
  });

  it("selects the requested TP bullet in a radio group without changing other fields", async () => {
    document.body.innerHTML = `
      <table>
        <tr><th>Nama</th><th>Other</th><th>Tahap Penguasaan*</th></tr>
        <tr>
          <td>STUDENT ALPHA</td>
          <td><input value="1.1"></td>
          <td>
            <label><input type="radio" name="alpha-tp" value="1">1</label>
            <label><input type="radio" name="alpha-tp" value="2">2</label>
            <label><input type="radio" name="alpha-tp" value="3">3</label>
            <label><input type="radio" name="alpha-tp" value="4">4</label>
            <label><input type="radio" name="alpha-tp" value="5">5</label>
            <label><input type="radio" name="alpha-tp" value="6">6</label>
          </td>
          <td><textarea></textarea></td>
        </tr>
      </table>`;

    const results = await fillStudentTpRecords([{ name: "STUDENT ALPHA", tp: 4 }]);

    expect(results[0].filled).toBe(true);
    expect(Array.from(document.querySelectorAll<HTMLInputElement>('input[type="radio"]'))
      .map(input => input.checked)).toEqual([false, false, false, true, false, false]);
    expect((document.querySelector('input:not([type="radio"])') as HTMLInputElement).value).toBe("1.1");
    expect((document.querySelector("textarea") as HTMLTextAreaElement).value).toBe("");
  });

  it("reads MOEIS custom radio selection from aria-checked and wrapper state", async () => {
    document.body.innerHTML = `
      <table>
        <tr><th>Nama</th><th>Tahap Penguasaan*</th></tr>
        <tr><td>STUDENT ALPHA</td><td>
          ${[1, 2, 3, 4, 5, 6].map(tp => `
            <div class="w-form-el w-radio w-radio--${tp === 4 ? "checked" : "unchecked"}">
              <label><input type="radio" role="radio" aria-checked="${tp === 4}" name="custom-tp" value="on">TP${tp}</label>
            </div>`).join("")}
        </td></tr>
      </table>`;
    const radios = Array.from(document.querySelectorAll<HTMLInputElement>('input[type="radio"]'));
    radios.forEach(radio => {
      radio.labels?.[0]?.addEventListener("click", () => {
        radios.forEach(item => {
          const selected = item === radio;
          item.setAttribute("aria-checked", String(selected));
          item.closest(".w-radio")!.className =
            `w-form-el w-radio w-radio--${selected ? "checked" : "unchecked"}`;
        });
      });
    });

    const result = await fillStudentTpRecords([{ name: "STUDENT ALPHA", tp: 4 }]);

    expect(result[0].filled).toBe(true);
    expect(radios.every(radio => !radio.checked)).toBe(true);
    expect(radios.filter(radio => radio.getAttribute("aria-checked") === "true"))
      .toEqual([radios[3]]);
  });

  it("matches by student ID and fills Kemahiran, TP, and Usaha Murid", async () => {
    document.body.innerHTML = `
      <table>
        <tr>
          <th>Nama</th><th>ID Pengenalan</th><th>Kemahiran*</th>
          <th>Tahap Penguasaan*</th><th>Usaha Murid*</th>
        </tr>
        <tr>
          <td>MOEIS NAME</td><td>ID-A</td>
          <td>
            <label><input type="checkbox" value="listening">LISTENING</label>
            <label><input type="checkbox" value="speaking">SPEAKING</label>
            <label><input type="checkbox" value="reading">READING</label>
            <label><input type="checkbox" value="writing">WRITING</label>
          </td>
          <td>
            <label><input type="radio" name="tp-a" value="1">1</label>
            <label><input type="radio" name="tp-a" value="2">2</label>
            <label><input type="radio" name="tp-a" value="3">3</label>
            <label><input type="radio" name="tp-a" value="4">4</label>
            <label><input type="radio" name="tp-a" value="5">5</label>
            <label><input type="radio" name="tp-a" value="6">6</label>
          </td>
          <td><select><option value="">Pilih</option><option>SANGAT TINGGI</option><option>TINGGI</option><option>SEDERHANA</option><option>RENDAH</option></select></td>
        </tr>
        <tr><td>OTHER NAME</td><td>ID-MISSING</td><td></td><td></td><td></td></tr>
      </table>`;

    const results = await fillStudentTpRecords([{ name: "RPH NAME", id: "ID-A", tp: 5 }]);

    expect(results[0].filled).toBe(true);
    expect(Array.from(document.querySelectorAll<HTMLInputElement>('input[type="checkbox"]'))
      .every(input => input.checked)).toBe(true);
    expect(document.querySelector<HTMLInputElement>('input[type="radio"][value="5"]')?.checked).toBe(true);
    expect(Array.from(document.querySelectorAll("select")).map(select => select.value)).toEqual(["TINGGI"]);
    expect(results[0]).toMatchObject({ fieldsFilled: 3, fieldsTotal: 3 });
    expect(results[1].error).toBe("No unambiguous TP found in Rekod Transit");
  });

  it("saves Kemahiran before TP and fills Usaha Murid", async () => {
    document.body.innerHTML = `
      <table>
        <tr><th>Bil.</th><th>Nama</th><th>ID Pengenalan</th><th>Jantina</th><th>Kemahiran*</th><th>Tahap Penguasaan*</th><th>Intervensi</th><th>Usaha Murid*</th><th>Status</th></tr>
        <tr>
          <td>1</td><td>STUDENT ALPHA</td><td>ID-A</td><td>P</td>
          <td><div class="w-flex"><i class="w-icon fa fa-pencil-square-o"></i></div></td>
          <td>${[1, 2, 3, 4, 5, 6].map(tp => `<label><input type="radio" name="main-tp" value="${tp}">TP${tp}</label>`).join("")}</td>
          <td><div class="w-flex"><i class="w-icon fa fa-pencil-square-o"></i></div></td>
          <td><div class="w-select"><div class="w-select__selection-wrap" role="button" aria-haspopup="listbox"><input class="w-select__selection" readonly><input type="hidden"></div><div class="w-menu-wrap"></div></div></td>
          <td></td>
        </tr>
      </table>`;

    const [skillIcon, interventionIcon] = Array.from(
      document.querySelectorAll<HTMLElement>("i.fa-pencil-square-o"),
    );
    const assessmentRow = document.querySelector("table tr:nth-child(2)")!;
    const skillCell = assessmentRow.cells[4];
    const interventionCell = assessmentRow.cells[6];
    skillIcon.addEventListener("click", () => {
      const editor = document.createElement("section");
      editor.innerHTML = `${["LISTENING", "SPEAKING", "READING", "WRITING"].map((skill, i) => `
        <fieldset><legend>${skill}</legend>
          ${[1, 2, 3, 4, 5, 6].map(tp => `<label><input type="radio" name="skill-${i}" value="${tp}">TP${tp}</label>`).join("")}
        </fieldset>`).join("")}
        <button>Simpan</button>`;
      editor.querySelector("button")!.addEventListener("click", () => {
        skillCell.dataset.savedSkills = Array.from(editor.querySelectorAll<HTMLInputElement>("input:checked"))
          .map(input => input.value).join(",");
        skillCell.querySelector<HTMLElement>("i")!.style.backgroundColor = "mediumseagreen";
        editor.remove();
      });
      document.body.append(editor);
    });
    interventionIcon.addEventListener("click", () => {
      const editor = document.createElement("section");
      editor.innerHTML = '<label>Keterangan<textarea></textarea></label><button>Simpan</button>';
      editor.querySelector("button")!.addEventListener("click", () => {
        interventionCell.dataset.savedText = (editor.querySelector("textarea") as HTMLTextAreaElement).value;
        interventionCell.querySelector<HTMLElement>("i")!.style.backgroundColor = "mediumseagreen";
        editor.remove();
      });
      document.body.append(editor);
    });

    const effortWrap = document.querySelector<HTMLElement>(".w-select__selection-wrap")!;
    effortWrap.addEventListener("click", () => {
      const menu = document.querySelector<HTMLElement>(".w-menu-wrap")!;
      menu.replaceChildren(...["SANGAT TINGGI", "TINGGI", "SEDERHANA", "RENDAH"].map(label => {
        const option = document.createElement("div");
        option.textContent = label;
        option.addEventListener("click", () => {
          (effortWrap.querySelector(".w-select__selection") as HTMLInputElement).value = label;
          (effortWrap.querySelector('input[type="hidden"]') as HTMLInputElement).value = label;
          menu.replaceChildren();
        });
        return option;
      }));
    });

    const results = await fillStudentTpRecords([{ name: "RPH ALPHA", id: "ID-A", tp: 3 }]);

    expect(results[0].filled).toBe(true);
    expect(results[0].error).toBeUndefined();
    expect(results[0].fieldsFilled).toBe(4);
    expect(results[0].fieldsTotal).toBe(4);
    expect(document.querySelector<HTMLInputElement>('input[name="main-tp"][value="3"]')?.checked).toBe(true);
    expect(skillCell.dataset.savedSkills).toBe("3,3,3,3");
    expect(interventionCell.dataset.savedText).toContain("bertutur");
    expect((effortWrap.querySelector(".w-select__selection") as HTMLInputElement).value).toBe("SEDERHANA");
  });

  it("sets all four skills to the RPH TP, saves Kemahiran, then sets Tahap Penguasaan only", async () => {
    document.body.innerHTML = `
      <table>
        <tr><th>Nama</th><th>Kemahiran*</th><th>Tahap Penguasaan*</th><th>Usaha Murid*</th></tr>
        <tr><td>AIDEN</td><td><i class="fa-pencil-square-o"></i></td>
          <td>${[1, 2, 3, 4, 5, 6].map(tp => `
            <div class="w-radio w-radio--unchecked"><label>
              <input type="radio" role="radio" aria-checked="false" name="overall" value="on">TP${tp}
            </label></div>`).join("")}
          </td>
          <td><div class="w-select"><div class="w-select__selection-wrap" role="button" aria-haspopup="listbox">
            <input class="w-select__selection" readonly value=""><input type="hidden"></div><div class="w-menu-wrap"></div></div></td>
        </tr>
      </table>`;

    const events: string[] = [];
    const tpRadios = Array.from(document.querySelectorAll<HTMLInputElement>('input[name="overall"]'));
    tpRadios.forEach(radio => radio.labels?.[0]?.addEventListener("click", () => {
      tpRadios.forEach(item => {
        const selected = item === radio;
        item.setAttribute("aria-checked", String(selected));
        item.closest(".w-radio")!.className = `w-radio w-radio--${selected ? "checked" : "unchecked"}`;
      });
      events.push(`tp:${radio.labels?.[0]?.textContent?.trim()}`);
    }));

    const skillCell = document.querySelector<HTMLTableCellElement>("tr:nth-child(2) td:nth-child(2)")!;
    const pencil = skillCell.querySelector<HTMLElement>("i")!;
    pencil.addEventListener("click", () => {
      const editor = document.createElement("section");
      editor.innerHTML = ["LISTENING", "SPEAKING", "READING", "WRITING"].map((skill, index) => `
        <div class="skill-group"><strong>${skill}</strong>${[1, 2, 3, 4, 5, 6].map(tp => `
          <div class="w-radio w-radio--unchecked"><label>
            <input type="radio" role="radio" aria-checked="false" name="skill-${index}" value="on">TP${tp}
          </label></div>`).join("")}</div>`).join("") + "<button>Simpan</button>";
      editor.querySelectorAll<HTMLInputElement>('input[type="radio"]').forEach(radio => {
        radio.labels?.[0]?.addEventListener("click", () => {
          const group = radio.closest(".skill-group")!;
          group.querySelectorAll<HTMLInputElement>('input[type="radio"]').forEach(item => {
            const selected = item === radio;
            item.setAttribute("aria-checked", String(selected));
            item.closest(".w-radio")!.className = `w-radio w-radio--${selected ? "checked" : "unchecked"}`;
          });
        });
      });
      editor.querySelector("button")!.addEventListener("click", () => {
        const chosen = Array.from(editor.querySelectorAll<HTMLInputElement>('input[aria-checked="true"]'));
        skillCell.dataset.savedSkills = chosen.map(item => item.labels?.[0]?.textContent?.trim()).join(",");
        pencil.style.backgroundColor = "mediumseagreen";
        events.push(`save:${chosen.length}`);
        editor.remove();
      });
      document.body.append(editor);
    });

    const effortWrap = document.querySelector<HTMLElement>(".w-select__selection-wrap")!;
    effortWrap.addEventListener("click", () => {
      const menu = document.querySelector<HTMLElement>(".w-menu-wrap")!;
      menu.replaceChildren(...["SANGAT TINGGI", "TINGGI", "SEDERHANA", "RENDAH"].map(label => {
        const option = document.createElement("div");
        option.textContent = label;
        option.addEventListener("click", () => {
          (effortWrap.querySelector(".w-select__selection") as HTMLInputElement).value = label;
          (effortWrap.querySelector('input[type="hidden"]') as HTMLInputElement).value = label;
          menu.replaceChildren();
        });
        return option;
      }));
    });

    const result = await fillStudentTpRecords([{ name: "AIDEN", tp: 3 }]);

    expect(skillCell.dataset.savedSkills).toBe("TP3,TP3,TP3,TP3");
    expect(events).toContain("save:4");
    expect(events.indexOf("save:4")).toBeLessThan(events.indexOf("tp:TP3"));
    expect(tpRadios.find(radio => radio.getAttribute("aria-checked") === "true")?.labels?.[0]?.textContent?.trim())
      .toBe("TP3");
    expect(result[0]).toMatchObject({ filled: true, fieldsFilled: 3, fieldsTotal: 3, tp: 3 });
    expect(document.querySelector('[data-field="intervensi"]')?.getAttribute("style")).toBeUndefined();
    expect((document.querySelector(".w-select__selection") as HTMLInputElement).value).toBe("SEDERHANA");
  });

  it.each([
    { tp: 1, effort: "RENDAH" },
    { tp: 2, effort: "RENDAH" },
    { tp: 3, effort: "SEDERHANA" },
    { tp: 4, effort: "SEDERHANA" },
    { tp: 5, effort: "TINGGI" },
    { tp: 6, effort: "SANGAT TINGGI" },
  ])("selects Usaha Murid $effort for TP $tp", async ({ tp, effort }) => {
    document.body.innerHTML = `
      <table>
        <tr><th>Nama</th><th>Tahap Penguasaan</th><th>Usaha Murid</th></tr>
        <tr><td>STUDENT ALPHA</td><td><input value="${tp}"></td>
          <td><select><option value="">Pilih</option><option>SANGAT TINGGI</option><option>TINGGI</option><option>SEDERHANA</option><option>RENDAH</option></select></td></tr>
      </table>`;

    const results = await fillStudentTpRecords([{ name: "STUDENT ALPHA", tp }]);

    expect(results[0].filled).toBe(true);
    expect(results[0].fieldsFilled).toBe(2);
    expect(results[0].fieldsTotal).toBe(2);
    expect((document.querySelector("select") as HTMLSelectElement).value).toBe(effort);
  });

  it("opens the Usaha Murid dropdown, selects the TP-based option, and moves to the next pupil", async () => {
    document.body.innerHTML = `
      <table>
        <tr><th>Nama</th><th>Tahap Penguasaan</th><th>Usaha Murid</th></tr>
        <tr><td>STUDENT ALPHA</td><td><input value="5"></td>
          <td><div class="w-select"><div class="w-select__selection-wrap" role="button" aria-haspopup="listbox">
            <input class="w-select__selection" readonly value=""><input type="hidden"></div><div class="w-menu-wrap"></div></div></td></tr>
        <tr><td>STUDENT BETA</td><td><input value="2"></td>
          <td><div class="w-select"><div class="w-select__selection-wrap" role="button" aria-haspopup="listbox">
            <input class="w-select__selection" readonly value=""><input type="hidden"></div><div class="w-menu-wrap"></div></div></td></tr>
      </table>`;

    for (const wrap of Array.from(document.querySelectorAll<HTMLElement>(".w-select__selection-wrap"))) {
      const menu = wrap.closest(".w-select")!.querySelector<HTMLElement>(".w-menu-wrap")!;
      wrap.addEventListener("click", () => {
        menu.replaceChildren(...["SANGAT TINGGI", "TINGGI", "SEDERHANA", "RENDAH"].map(label => {
          const option = document.createElement("div");
          option.textContent = label;
          option.addEventListener("click", () => {
            (wrap.querySelector(".w-select__selection") as HTMLInputElement).value = label;
            (wrap.querySelector('input[type="hidden"]') as HTMLInputElement).value = label;
            menu.replaceChildren();
          });
          return option;
        }));
      });
    }

    const results = await fillStudentTpRecords([
      { name: "STUDENT ALPHA", tp: 5 },
      { name: "STUDENT BETA", tp: 2 },
    ]);

    expect(results.every(result => result.filled)).toBe(true);
    expect(Array.from(document.querySelectorAll<HTMLInputElement>(".w-select__selection"))
      .map(input => input.value)).toEqual(["TINGGI", "RENDAH"]);
  });

  it("fills all five categories for a pupil and reports complete", async () => {
    const comment = "MURID MENUNJUKKAN PRESTASI YANG MEMUASKAN.";
    document.body.innerHTML = `
      <table>
        <tr><th>Nama</th><th>Kemahiran</th><th>Tahap Penguasaan</th><th>Ulasan Guru</th><th>Intervensi</th><th>Usaha Murid</th></tr>
        <tr><td>STUDENT ALPHA</td>
          <td><i class="fa-pencil-square-o" data-editor="skills"></i></td>
          <td><input value="4"></td>
          <td><i class="fa-pencil-square-o" data-editor="comment"></i></td>
          <td><i class="fa-pencil-square-o" data-editor="intervention"></i></td>
          <td><select><option value="">Pilih</option><option>SANGAT TINGGI</option><option>TINGGI</option><option>SEDERHANA</option><option>RENDAH</option></select></td>
        </tr>
      </table>`;
    const row = document.querySelector("table tr:nth-child(2)")!;
    const skillCell = row.cells[1];
    const commentCell = row.cells[3];
    const interventionCell = row.cells[4];
    document.querySelector('[data-editor="skills"]')!.addEventListener("click", () => {
      const editor = document.createElement("section");
      editor.innerHTML = ["LISTENING", "SPEAKING", "READING", "WRITING"].map((skill, index) => `
        <fieldset><legend>${skill}</legend>
          <label><input type="radio" name="skill-${index}" value="4">4</label>
        </fieldset>`).join("") + "<button>Simpan</button>";
      editor.querySelector("button")!.addEventListener("click", () => {
        skillCell.querySelector<HTMLElement>("i")!.style.backgroundColor = "mediumseagreen";
        editor.remove();
      });
      document.body.append(editor);
    });
    document.querySelector('[data-editor="comment"]')!.addEventListener("click", () => {
      const editor = document.createElement("section");
      editor.innerHTML = `
        <div>Kategori</div>
        ${["LEMAH", "SEDERHANA", "CEMERLANG"].map(category =>
          `<label><input type="radio" name="category" value="${category}">${category}</label>`,
        ).join("")}
        <div>Ulasan</div>
        <div class="picker"><div role="option">${comment}</div><button>Pilih</button></div>
        <div class="selected-comment"></div>
        <button class="save">Simpan</button>`;
      editor.querySelector(".picker button")!.addEventListener("click", () => {
        editor.querySelector(".selected-comment")!.textContent = comment;
        editor.querySelector(".picker")!.remove();
      });
      editor.querySelector(".save")!.addEventListener("click", () => {
        commentCell.dataset.category = editor.querySelector<HTMLInputElement>('input[name="category"]:checked')?.value;
        commentCell.querySelector<HTMLElement>("i")!.style.backgroundColor = "mediumseagreen";
        editor.remove();
      });
      document.body.append(editor);
    });
    document.querySelector('[data-editor="intervention"]')!.addEventListener("click", () => {
      const editor = document.createElement("section");
      editor.innerHTML = '<label>Keterangan<textarea></textarea></label><button>Simpan</button>';
      editor.querySelector("button")!.addEventListener("click", () => {
        interventionCell.dataset.savedText = (editor.querySelector("textarea") as HTMLTextAreaElement).value;
        interventionCell.querySelector<HTMLElement>("i")!.style.backgroundColor = "mediumseagreen";
        editor.remove();
      });
      document.body.append(editor);
    });

    const results = await fillStudentTpRecords([{ name: "STUDENT ALPHA", tp: 4 }]);

    expect(results[0]).toMatchObject({ filled: true, fieldsFilled: 5, fieldsTotal: 5 });
    expect(results[0].error).toBeUndefined();
    expect(commentCell.dataset.category).toBe("SEDERHANA");
    expect((document.querySelector("select") as HTMLSelectElement).value).toBe("SEDERHANA");
    expect(interventionCell.dataset.savedText).toContain("mendengar");
  });

  it("selects the Ulasan category when MOEIS renders it as clickable wrappers instead of radios", async () => {
    const comment = "MURID SENTIASA MENUNJUKKAN USAHA YANG BAIK.";
    document.body.innerHTML = `
      <table>
        <tr><th>Nama</th><th>Tahap Penguasaan</th><th>Ulasan Guru</th></tr>
        <tr><td>STUDENT ALPHA</td><td><input value="6"></td><td><i class="fa-pencil-square-o"></i></td></tr>
      </table>`;
    const cell = document.querySelector<HTMLTableCellElement>("td:nth-child(3)")!;
    cell.querySelector("i")!.addEventListener("click", () => {
      const editor = document.createElement("section");
      editor.innerHTML = `
        <div>Kategori</div>
        ${["LEMAH", "SEDERHANA", "CEMERLANG"].map(category =>
          `<div class="w-radio" data-category="${category}"><span>${category}</span></div>`,
        ).join("")}
        <div>Ulasan</div>
        <button class="folder">folder</button>
        <div class="picker" hidden><div role="option">${comment}</div><button>Pilih</button></div>
        <button class="save">Simpan</button>`;
      editor.querySelectorAll<HTMLElement>(".w-radio").forEach(wrapper => {
        wrapper.addEventListener("click", () => {
          editor.querySelectorAll(".w-radio").forEach(item => {
            item.className = `w-radio${item === wrapper ? " w-radio--checked" : ""}`;
          });
        });
      });
      editor.querySelector(".folder")!.addEventListener("click", () => {
        editor.querySelector<HTMLElement>(".picker")!.hidden = false;
      });
      editor.querySelector(".picker button")!.addEventListener("click", () => {
        editor.querySelector<HTMLElement>(".picker")!.hidden = true;
      });
      editor.querySelector(".save")!.addEventListener("click", () => {
        cell.dataset.savedCategory = editor.querySelector<HTMLElement>(".w-radio--checked")?.dataset.category;
        cell.querySelector<HTMLElement>("i")!.style.backgroundColor = "mediumseagreen";
        editor.remove();
      });
      document.body.append(editor);
    });

    const results = await fillStudentTpRecords([{ name: "STUDENT ALPHA", tp: 6 }]);

    expect(results[0].filled).toBe(true);
    expect(cell.dataset.savedCategory).toBe("CEMERLANG");
  });

  it("selects Usaha Murid through a separate arrow button that opens a body-level menu", async () => {
    document.body.innerHTML = `
      <table>
        <tr><th>Nama</th><th>Tahap Penguasaan</th><th>Usaha Murid</th></tr>
        <tr><td>STUDENT ALPHA</td><td><input value="5"></td>
          <td><div class="w-select"><input class="w-select__selection" readonly value="">
            <button class="arrow" type="button">v</button></div></td></tr>
      </table>`;
    const arrow = document.querySelector<HTMLButtonElement>(".arrow")!;
    const selection = document.querySelector<HTMLInputElement>(".w-select__selection")!;
    arrow.addEventListener("click", () => {
      const menu = document.createElement("div");
      menu.setAttribute("role", "listbox");
      menu.innerHTML = ["SANGAT TINGGI", "TINGGI", "SEDERHANA", "RENDAH"]
        .map(label => `<div role="option">${label}</div>`).join("");
      menu.querySelectorAll<HTMLElement>('[role="option"]').forEach(option => {
        option.addEventListener("click", () => {
          selection.value = option.textContent ?? "";
          menu.remove();
        });
      });
      document.body.append(menu);
    });

    const results = await fillStudentTpRecords([{ name: "STUDENT ALPHA", tp: 5 }]);

    expect(results[0].filled).toBe(true);
    expect(selection.value).toBe("TINGGI");
  });

  it("opens and saves hidden Kemahiran and Ulasan editors", async () => {
    const comment = "MURID MENUNJUKKAN PRESTASI YANG SEMAKIN MENINGKAT.";
    document.body.innerHTML = `
      <table>
        <tr><th>Nama</th><th>Kemahiran*</th><th>Tahap Penguasaan*</th><th>Ulasan Guru*</th></tr>
        <tr><td>STUDENT ALPHA</td><td><i class="fa-pencil-square-o" data-editor="skills"></i></td>
          <td><div class="w-radio w-radio--unchecked"><label><input type="radio" name="main" value="on" role="radio" aria-checked="false">TP 3</label></div></td>
          <td><i class="fa-pencil-square-o" data-editor="comment"></i></td></tr>
      </table>
      <section id="skills-editor" hidden>
        ${["LISTENING", "SPEAKING", "READING", "WRITING"].map(skill => `
          <div class="skill-group"><strong>${skill}</strong>
            ${[1, 2, 3, 4, 5, 6].map(tp =>
              `<div class="w-radio w-radio--unchecked"><label><input type="radio" name="${skill}-${tp}" value="on" role="radio" aria-checked="false">TP${tp}</label></div>`,
            ).join("")}
          </div>`).join("")}
        <button>Simpan</button>
      </section>
      <section id="comment-editor" hidden>
        <fieldset><legend>Kategori</legend>
          ${["LEMAH", "SEDERHANA", "CEMERLANG"].map(category => `
            <div class="w-radio w-radio--unchecked"><label><input type="radio" name="category" value="on" role="radio" aria-checked="false">${category}</label></div>
          `).join("")}
        </fieldset>
        <div>Ulasan <button class="folder">folder</button></div>
        <div class="comment-display"></div>
        <div class="comment-picker" hidden><div role="option">${comment}</div><button>Pilih</button></div>
        <button class="save">Simpan</button>
      </section>`;

    const skillsEditor = document.querySelector<HTMLElement>("#skills-editor")!;
    const commentEditor = document.querySelector<HTMLElement>("#comment-editor")!;
    document.querySelectorAll<HTMLInputElement>('input[type="radio"]').forEach(radio => {
      radio.labels?.[0]?.addEventListener("click", () => {
        const group = radio.closest(".skill-group") ?? radio.closest("fieldset") ?? radio.closest("td");
        if (!group) return;
        group.querySelectorAll<HTMLInputElement>('input[type="radio"]').forEach(item => {
          item.setAttribute("aria-checked", String(item === radio));
          item.closest(".w-radio")!.className = `w-radio ${item === radio ? "w-radio--checked" : "w-radio--unchecked"}`;
        });
      });
    });
    document.querySelector('[data-editor="skills"]')!.addEventListener("click", () => {
      skillsEditor.hidden = false;
    });
    document.querySelector('[data-editor="comment"]')!.addEventListener("click", () => {
      commentEditor.hidden = false;
    });
    skillsEditor.querySelector("button")!.addEventListener("click", () => {
      document.querySelector<HTMLElement>('[data-editor="skills"]')!.style.backgroundColor = "mediumseagreen";
      skillsEditor.hidden = true;
    });
    commentEditor.querySelector(".folder")!.addEventListener("click", () => {
      const picker = commentEditor.querySelector<HTMLElement>(".comment-picker")!;
      picker.hidden = false;
      const option = picker.querySelector<HTMLElement>('[role="option"]')!;
      option.addEventListener("click", () => {
        picker.dataset.selected = comment;
      });
      picker.querySelector("button")!.addEventListener("click", () => {
        commentEditor.querySelector(".comment-display")!.textContent = picker.dataset.selected ?? "";
        picker.hidden = true;
      });
    });
    commentEditor.querySelector(".save")!.addEventListener("click", () => {
      document.querySelector<HTMLElement>('[data-editor="comment"]')!.style.backgroundColor = "mediumseagreen";
      commentEditor.dataset.savedComment = commentEditor.querySelector(".comment-display")!.textContent ?? "";
      commentEditor.hidden = true;
    });

    const results = await fillStudentTpRecords([{ name: "STUDENT ALPHA", tp: 3 }]);

    expect(results[0].error).toBeUndefined();
    expect(results[0].filled).toBe(true);
    expect(skillsEditor.querySelectorAll<HTMLInputElement>('input[aria-checked="true"]'))
      .toHaveLength(4);
    expect(commentEditor.hidden).toBe(true);
    expect(commentEditor.querySelector<HTMLInputElement>('input[type="radio"][aria-checked="true"]')?.labels?.[0]?.textContent)
      .toBe("SEDERHANA");
    expect(document.querySelector<HTMLInputElement>('td input[aria-checked="true"]')).not.toBeNull();
    expect(commentEditor.dataset.savedComment).toBe(comment);
  });

  it("updates Usaha Murid from the latest TP during transfer", async () => {
    document.body.innerHTML = `
      <table>
        <tr><th>Nama</th><th>Tahap Penguasaan*</th><th>Usaha Murid*</th></tr>
        <tr><td>STUDENT ALPHA</td><td>
          <input value="3">
        </td><td>
          <div class="w-select">
            <div class="w-select__selection-wrap" role="button" aria-haspopup="listbox">
              <input class="w-select__selection" readonly value="TINGGI">
              <input type="hidden" value="TINGGI">
            </div>
            <div class="w-menu-wrap"></div>
          </div>
        </td></tr>
      </table>`;
    const wrap = document.querySelector<HTMLElement>(".w-select__selection-wrap")!;
    wrap.addEventListener("click", () => {
      const menu = document.querySelector<HTMLElement>(".w-menu-wrap")!;
      menu.replaceChildren(...["SANGAT TINGGI", "TINGGI", "SEDERHANA", "RENDAH"].map(label => {
        const option = document.createElement("div");
        option.textContent = label;
        option.addEventListener("click", () => {
          (wrap.querySelector(".w-select__selection") as HTMLInputElement).value = label;
          (wrap.querySelector('input[type="hidden"]') as HTMLInputElement).value = label;
          menu.replaceChildren();
        });
        return option;
      }));
    });
    const results = await fillStudentTpRecords([{ name: "STUDENT ALPHA", tp: 3 }]);

    expect(results[0].filled).toBe(true);
    expect((wrap.querySelector(".w-select__selection") as HTMLInputElement).value).toBe("SEDERHANA");
  });

  it("fills an empty Usaha Murid selection from the latest TP", async () => {
    document.body.innerHTML = `
      <table>
        <tr><th>Nama</th><th>Tahap Penguasaan*</th><th>Usaha Murid*</th></tr>
        <tr><td>STUDENT ALPHA</td><td><input value="3"></td><td>
          <div class="w-select">
            <div class="w-select__selection-wrap" role="button" aria-haspopup="listbox">
              <input class="w-select__selection" readonly>
              <input type="hidden">
            </div>
            <div class="w-menu-wrap"></div>
          </div>
        </td></tr>
      </table>`;
    const wrap = document.querySelector<HTMLElement>(".w-select__selection-wrap")!;
    wrap.addEventListener("click", () => {
      const menu = document.querySelector<HTMLElement>(".w-menu-wrap")!;
      menu.replaceChildren(...["SANGAT TINGGI", "TINGGI", "SEDERHANA", "RENDAH"].map(label => {
        const option = document.createElement("div");
        option.textContent = label;
        option.addEventListener("click", () => {
          (wrap.querySelector(".w-select__selection") as HTMLInputElement).value = label;
          (wrap.querySelector('input[type="hidden"]') as HTMLInputElement).value = label;
          menu.replaceChildren();
        });
        return option;
      }));
    });

    const results = await fillStudentTpRecords([{ name: "STUDENT ALPHA", tp: 3 }]);

    expect(results[0].filled).toBe(true);
    expect((wrap.querySelector(".w-select__selection") as HTMLInputElement).value).toBe("SEDERHANA");
  });

  it.each([
    { tp: 1, words: ["pemulihan", "berpandu"] },
    { tp: 3, words: ["mendengar", "bertutur", "membaca", "menulis"] },
    { tp: 5, words: ["bahasa Inggeris", "perbualan", "bacaan", "penulisan"] },
  ])("writes and saves Malay Intervensi guidance for TP $tp", async ({ tp, words }) => {
    document.body.innerHTML = `
      <table>
        <tr><th>Nama</th><th>Tahap Penguasaan</th><th>Intervensi</th></tr>
        <tr><td>STUDENT ALPHA</td><td><input value="${tp}"></td><td><i class="fa-pencil-square-o"></i></td></tr>
      </table>`;
    const cell = document.querySelector<HTMLTableCellElement>("td:nth-child(3)")!;
    cell.querySelector("i")!.addEventListener("click", () => {
      const editor = document.createElement("section");
      editor.innerHTML = '<label>Keterangan<textarea></textarea></label><button>Simpan</button>';
      editor.querySelector("button")!.addEventListener("click", () => {
        cell.dataset.savedText = (editor.querySelector("textarea") as HTMLTextAreaElement).value;
        cell.querySelector<HTMLElement>("i")!.style.backgroundColor = "mediumseagreen";
        editor.remove();
      });
      document.body.append(editor);
    });

    const results = await fillStudentTpRecords([{ name: "STUDENT ALPHA", tp }]);
    const savedText = cell.dataset.savedText ?? "";

    expect(results[0].filled).toBe(true);
    expect(results[0].fieldsTotal).toBe(2);
    expect(words.every(word => savedText.toLowerCase().includes(word.toLowerCase()))).toBe(true);
  });

  it("retries an incomplete TP field after its options load", async () => {
    document.body.innerHTML = `
      <table>
        <tr><th>Nama</th><th>Tahap Penguasaan</th></tr>
        <tr><td>STUDENT ALPHA</td><td><select><option value="">Pilih</option></select></td></tr>
      </table>`;
    const select = document.querySelector<HTMLSelectElement>("select")!;
    window.setTimeout(() => {
      const option = document.createElement("option");
      option.textContent = "TP 4";
      option.value = "4";
      select.add(option);
    }, 50);

    const results = await fillStudentTpRecords([{ name: "STUDENT ALPHA", tp: 4 }]);

    expect(results[0].filled).toBe(true);
    expect(select.value).toBe("4");
  });

  it("closes an incomplete Intervensi editor and retries the fill", async () => {
    document.body.innerHTML = `
      <table>
        <tr><th>Nama</th><th>Tahap Penguasaan</th><th>Intervensi</th></tr>
        <tr><td>STUDENT ALPHA</td><td><input value="2"></td><td><i class="fa-pencil-square-o"></i></td></tr>
      </table>`;
    const cell = document.querySelector<HTMLTableCellElement>("td:nth-child(3)")!;
    let opens = 0;
    let closed = 0;
    cell.querySelector("i")!.addEventListener("click", () => {
      opens += 1;
      const editor = document.createElement("section");
      editor.innerHTML = opens === 1
        ? '<div>Keterangan</div><button>Simpan</button><button class="close">Tutup</button>'
        : '<label>Keterangan<textarea></textarea></label><button>Simpan</button>';
      editor.querySelector(".close")?.addEventListener("click", () => {
        closed += 1;
        editor.hidden = true;
      });
      editor.querySelector("button:not(.close)")!.addEventListener("click", () => {
        cell.dataset.savedText = (editor.querySelector("textarea") as HTMLTextAreaElement).value;
        cell.querySelector<HTMLElement>("i")!.style.backgroundColor = "mediumseagreen";
        editor.remove();
      });
      document.body.append(editor);
    });

    const results = await fillStudentTpRecords([{ name: "STUDENT ALPHA", tp: 2 }]);

    expect(results[0].filled).toBe(true);
    expect(opens).toBe(2);
    expect(closed).toBe(1);
    expect(cell.dataset.savedText).toContain("pemulihan");
  });

  it("replaces outdated Intervensi text with guidance for the latest TP", async () => {
    document.body.innerHTML = `
      <table>
        <tr><th>Nama</th><th>Tahap Penguasaan</th><th>Intervensi</th></tr>
        <tr><td>STUDENT ALPHA</td><td><input value="2"></td><td><i class="fa-pencil-square-o"></i></td></tr>
      </table>`;
    const cell = document.querySelector<HTMLTableCellElement>("td:nth-child(3)")!;
    cell.querySelector("i")!.addEventListener("click", () => {
      const editor = document.createElement("section");
      editor.innerHTML = '<label>Keterangan<textarea>Intervensi lama untuk TP1</textarea></label><button>Simpan</button>';
      editor.querySelector("button")!.addEventListener("click", () => {
        cell.dataset.savedText = (editor.querySelector("textarea") as HTMLTextAreaElement).value;
        cell.querySelector<HTMLElement>("i")!.style.backgroundColor = "mediumseagreen";
        editor.remove();
      });
      document.body.append(editor);
    });

    const results = await fillStudentTpRecords([{ name: "STUDENT ALPHA", tp: 5 }]);

    expect(results[0].filled).toBe(true);
    expect(cell.dataset.savedText).toContain("autentik");
    expect(cell.dataset.savedText).not.toContain("Intervensi lama");
  });

  it("applies the overall TP to each skill radio group", async () => {
    document.body.innerHTML = `
      <table>
        <tr><th>Nama</th><th>Kemahiran*</th><th>Tahap Penguasaan*</th></tr>
        <tr><td>STUDENT ALPHA</td><td>
          ${["LISTENING", "SPEAKING", "READING", "WRITING"].map(skill => `
            <fieldset><legend>${skill}</legend>
              <label><input type="radio" name="${skill}" value="2">2</label>
              <label><input type="radio" name="${skill}" value="4">4</label>
            </fieldset>`).join("")}
        </td><td><input value="4"></td></tr>
      </table>`;

    const results = await fillStudentTpRecords([{ name: "STUDENT ALPHA", tp: 4 }]);

    expect(results[0].filled).toBe(true);
    expect(Array.from(document.querySelectorAll<HTMLInputElement>('input[type="radio"]:checked')))
      .toHaveLength(4);
    expect(Array.from(document.querySelectorAll<HTMLInputElement>('input[type="radio"]:checked'))
      .every(input => input.value === "4")).toBe(true);
  });

  it("updates an already selected TP radio bullet from the latest RPH", async () => {
    document.body.innerHTML = `
      <table>
        <tr><th>Nama</th><th>Tahap Penguasaan</th></tr>
        <tr><td>STUDENT ALPHA</td><td>
          <label><input type="radio" name="alpha-tp" value="3" checked>3</label>
          <label><input type="radio" name="alpha-tp" value="4">4</label>
        </td></tr>
      </table>`;

    const results = await fillStudentTpRecords([{ name: "STUDENT ALPHA", tp: 4 }]);

    expect(results[0].filled).toBe(true);
    expect(results[0].error).toBeUndefined();
    expect(Array.from(document.querySelectorAll<HTMLInputElement>('input[type="radio"]'))
      .map(input => input.checked)).toEqual([false, true]);
  });

  it("updates existing Kemahiran and overall TP selections from the latest RPH", async () => {
    document.body.innerHTML = `
      <table>
        <tr><th>Nama</th><th>Kemahiran</th><th>Tahap Penguasaan</th></tr>
        <tr><td>STUDENT ALPHA</td><td><i class="fa-pencil-square-o"></i></td><td>
          <label><input type="radio" name="overall" value="2" checked>TP2</label>
          <label><input type="radio" name="overall" value="4">TP4</label>
        </td></tr>
      </table>`;
    const skillCell = document.querySelector<HTMLTableCellElement>("td:nth-child(2)")!;
    const pencil = skillCell.querySelector<HTMLElement>("i")!;
    pencil.addEventListener("click", () => {
      const editor = document.createElement("section");
      editor.innerHTML = ["LISTENING", "SPEAKING", "READING", "WRITING"].map((skill, index) => `
        <fieldset><legend>${skill}</legend>
          ${[2, 4].map(tp => `<label><input type="radio" name="skill-${index}" value="${tp}"${tp === 2 ? " checked" : ""}>TP${tp}</label>`).join("")}
        </fieldset>`).join("") + "<button>Simpan</button>";
      editor.querySelector("button")!.addEventListener("click", () => {
        skillCell.dataset.savedSkills = Array.from(editor.querySelectorAll<HTMLInputElement>("input:checked"))
          .map(input => input.value).join(",");
        pencil.style.backgroundColor = "mediumseagreen";
        editor.remove();
      });
      document.body.append(editor);
    });

    const results = await fillStudentTpRecords([{ name: "STUDENT ALPHA", tp: 4 }]);

    expect(results[0].filled).toBe(true);
    expect(skillCell.dataset.savedSkills).toBe("4,4,4,4");
    expect(Array.from(document.querySelectorAll<HTMLInputElement>('input[name="overall"]'))
      .map(input => input.checked)).toEqual([false, true]);
  });

  it.each([
    { tp: 1, category: "LEMAH" },
    { tp: 4, category: "SEDERHANA" },
    { tp: 6, category: "CEMERLANG" },
  ])("selects a random Ulasan keterangan for TP $tp in category $category and saves it", async ({ tp, category }) => {
    const comments = ["KETERANGAN PILIHAN A", "KETERANGAN PILIHAN B"];
    document.body.innerHTML = `
      <table>
        <tr><th>Nama</th><th>Tahap Penguasaan</th><th>Ulasan Guru</th></tr>
        <tr><td>STUDENT ALPHA</td><td><input></td><td><i class="fa-pencil-square-o"></i></td></tr>
      </table>`;
    const ulasanCell = document.querySelector<HTMLTableCellElement>("td:nth-child(3)")!;
    const events: string[] = [];
    ulasanCell.querySelector("i")!.addEventListener("click", () => {
      const editor = document.createElement("section");
      editor.innerHTML = `
        <fieldset><legend>Kategori</legend>
          ${["LEMAH", "SEDERHANA", "CEMERLANG"].map(value =>
            `<label><input type="radio" name="category" value="${value}">${value}</label>`,
          ).join("")}
        </fieldset>
        <div>Ulasan <button class="folder">Pilih ulasan</button></div>
        <div class="selected-comment">COMMENT ALREADY ENTERED</div>
        <button class="save">Simpan</button>`;
      editor.querySelectorAll<HTMLInputElement>('input[name="category"]').forEach(radio => {
        radio.labels?.[0]?.addEventListener("click", () => {
          events.push(`category:${radio.value}`);
        });
      });
      editor.querySelector(".folder")!.addEventListener("click", () => {
        events.push("open-picker");
        const picker = document.createElement("section");
        picker.setAttribute("role", "dialog");
        picker.innerHTML = `${comments.map(comment => `<div role="option">${comment}</div>`).join("")}<button>Pilih</button>`;
        picker.querySelectorAll<HTMLElement>('[role="option"]').forEach(option => {
          option.addEventListener("click", () => {
            picker.dataset.selected = option.textContent ?? "";
            events.push(`comment:${option.textContent}`);
          });
        });
        picker.querySelector("button")!.addEventListener("click", () => {
          editor.querySelector(".selected-comment")!.textContent = picker.dataset.selected ?? "";
          events.push("choose");
          picker.remove();
        });
        document.body.append(picker);
      });
      editor.querySelector(".save")!.addEventListener("click", () => {
        ulasanCell.dataset.savedCategory = editor.querySelector<HTMLInputElement>("input:checked")?.value;
        ulasanCell.dataset.savedComment = editor.querySelector(".selected-comment")?.textContent ?? "";
        ulasanCell.querySelector<HTMLElement>("i")!.style.backgroundColor = "mediumseagreen";
        events.push("save");
        editor.remove();
      });
      document.body.append(editor);
    });

    const results = await fillStudentTpRecords([{ name: "STUDENT ALPHA", tp }]);

    expect(results[0].filled).toBe(true);
    expect(ulasanCell.dataset.savedCategory).toBe(category);
    expect(comments).toContain(ulasanCell.dataset.savedComment);
    expect(ulasanCell.dataset.savedComment).not.toBe("COMMENT ALREADY ENTERED");
    expect(events).toContain(`category:${category}`);
    expect(events.indexOf(`category:${category}`)).toBeLessThan(events.indexOf("open-picker"));
    expect(events.indexOf("open-picker")).toBeLessThan(events.findIndex(event => event.startsWith("comment:")));
    expect(events.findIndex(event => event.startsWith("comment:"))).toBeLessThan(events.indexOf("choose"));
    expect(events.indexOf("choose")).toBeLessThan(events.indexOf("save"));
  });

  it("identifies a TP radio by its visible label when its value is generic", async () => {
    document.body.innerHTML = `
      <table>
        <tr><th>Nama</th><th>Tahap Penguasaan</th></tr>
        <tr><td>STUDENT ALPHA</td><td>
          <label><input type="radio" name="alpha-tp" value="on">TP 1</label>
          <label><input type="radio" name="alpha-tp" value="on">TP 2</label>
          <label><input type="radio" name="alpha-tp" value="on">TP 3</label>
        </td></tr>
      </table>`;

    const results = await fillStudentTpRecords([{ name: "STUDENT ALPHA", tp: 2 }]);

    expect(results[0].filled).toBe(true);
    expect(Array.from(document.querySelectorAll<HTMLInputElement>('input[type="radio"]'))
      .map(input => input.checked)).toEqual([false, true, false]);
  });

  it("opens an accessible TP dropdown and chooses the matching TP option", async () => {
    document.body.innerHTML = `
      <div role="listbox"><div role="option">TP 3</div></div>
      <table>
        <tr><th>Nama</th><th>Tahap Penguasaan</th></tr>
        <tr><td>STUDENT ALPHA</td><td><button type="button" role="combobox" aria-haspopup="listbox">Pilih</button></td></tr>
      </table>`;
    const button = document.querySelector<HTMLButtonElement>("button")!;
    button.addEventListener("click", () => {
      const list = document.createElement("div");
      list.setAttribute("role", "listbox");
      list.innerHTML = '<div role="option" aria-selected="false">TP 3</div>';
      document.body.append(list);
      list.firstElementChild?.addEventListener("click", () => {
        button.textContent = "TP 3";
        list.remove();
      });
    });

    const results = await fillStudentTpRecords([{ name: "STUDENT ALPHA", tp: 3 }]);

    expect(results[0].filled).toBe(true);
    expect(button.textContent).toBe("TP 3");
  });

  it("does not fill when the opened TP dropdown has no exact matching option", async () => {
    document.body.innerHTML = `
      <table>
        <tr><th>Nama</th><th>Tahap Penguasaan</th></tr>
        <tr><td>STUDENT ALPHA</td><td><button type="button" role="combobox">Pilih</button></td></tr>
      </table>`;
    const button = document.querySelector<HTMLButtonElement>("button")!;
    button.addEventListener("click", () => {
      const list = document.createElement("div");
      list.setAttribute("role", "listbox");
      list.innerHTML = '<div role="option">TP 2</div>';
      document.body.append(list);
    });

    const results = await fillStudentTpRecords([{ name: "STUDENT ALPHA", tp: 3 }]);

    expect(results[0].filled).toBe(false);
    expect(results[0].error).toContain("TP dropdown opened, but no matching option appeared");
    expect(button.textContent).toBe("Pilih");
  }, 15000);

  it("updates existing TP and rejects ambiguous names or tables", async () => {
    document.body.innerHTML = `
      <table><tr><th>Nama</th><th>TP</th></tr>
        <tr><td>STUDENT ALPHA</td><td><input value="4"></td></tr>
        <tr><td>STUDENT BETA EXTRA</td><td><input></td></tr>
      </table>`;
    const result = await fillStudentTpRecords([
      { name: "STUDENT ALPHA", tp: 3 },
      { name: "STUDENT BETA", tp: 5 },
    ]);
    expect((document.querySelector("input") as HTMLInputElement).value).toBe("3");
    expect(result[0].filled).toBe(true);
    expect(result).toHaveLength(2);
    expect(result[1].filled).toBe(true);
    expect((document.querySelectorAll("input")[1] as HTMLInputElement).value).toBe("5");
  });

  it("does not fill duplicate target names when there is no unique ID", async () => {
    document.body.innerHTML = `
      <table><tr><th>Nama</th><th>TP</th></tr>
        <tr><td>STUDENT ALPHA</td><td><input></td></tr>
        <tr><td>STUDENT ALPHA</td><td><input></td></tr>
      </table>`;

    const results = await fillStudentTpRecords([{ name: "STUDENT ALPHA", tp: 3 }]);

    expect(results.every(result => result.error === "Student ID or name is not unique in MOEIS table")).toBe(true);
    expect(Array.from(document.querySelectorAll<HTMLInputElement>("input")).every(input => input.value === "")).toBe(true);
  });

  it("matches a uniquely closest student when the full name has a spelling typo", async () => {
    document.body.innerHTML = `
      <table><tr><th>Nama</th><th>TP</th></tr>
        <tr><td>NIHAHARIKA BINTI ABDUL MUHAIMIN</td><td><input></td></tr>
        <tr><td>PRITISHA SREE A P JAMES</td><td><input></td></tr>
      </table>`;

    const results = await fillStudentTpRecords([
      { name: "NIHAAHARIKA BINTI ABDUL MUHAIMIN", tp: 3 },
      { name: "PRITISHAA SREE A P JAMES", tp: 5 },
    ]);

    expect(results.every(result => result.filled)).toBe(true);
    expect(Array.from(document.querySelectorAll<HTMLInputElement>("input")).map(input => input.value))
      .toEqual(["3", "5"]);
  });

  it("matches reordered names with omitted names and spelling variants", async () => {
    document.body.innerHTML = `
      <table><tr><th>Nama</th><th>TP</th></tr>
        <tr><td>JIA WEI TAN</td><td><input></td></tr>
        <tr><td>NUR AISYAH BINTI MOHD YUSOF</td><td><input></td></tr>
      </table>`;

    const results = await fillStudentTpRecords([
      { name: "TAN JIA WEI", tp: 2 },
      { name: "AISYAH MOHAMMAD YUSUF", tp: 5 },
    ]);

    expect(results.every(result => result.filled)).toBe(true);
    expect(Array.from(document.querySelectorAll<HTMLInputElement>("input")).map(input => input.value))
      .toEqual(["2", "5"]);
  });

  it("does not guess between similarly matching reordered names", async () => {
    document.body.innerHTML = `
      <table><tr><th>Nama</th><th>TP</th></tr>
        <tr><td>JIA WEI TAN</td><td><input></td></tr>
      </table>`;

    const results = await fillStudentTpRecords([
      { name: "TAN JIA WEI", tp: 2 },
      { name: "WEI TAN JIA", tp: 5 },
    ]);

    expect(results[0].filled).toBe(false);
    expect(results[0].error).toContain("Multiple Rekod Transit TP records match");
    expect((document.querySelector("input") as HTMLInputElement).value).toBe("");
  });

  it("leaves a fuzzy name unchanged when two source students are similarly close", async () => {
    document.body.innerHTML = `
      <table><tr><th>Nama</th><th>TP</th></tr>
        <tr><td>AIDEN CHIN PARK YIM</td><td><input></td></tr>
      </table>`;

    const results = await fillStudentTpRecords([
      { name: "AIDEN CHIN PARK YIN", tp: 3 },
      { name: "AIDEN CHIN PARK YINN", tp: 4 },
    ]);

    expect(results[0].filled).toBe(false);
    expect(results[0].error).toContain("Multiple Rekod Transit TP records match");
    expect((document.querySelector("input") as HTMLInputElement).value).toBe("");
  });

  it("chooses the MOEIS class table with the greatest exact-name overlap", async () => {
    document.body.innerHTML = `
      <table>
        <tr><th>Nama</th><th>TP</th></tr>
        <tr><td>OTHER STUDENT</td><td><input></td></tr>
      </table>
      <table>
        <tr><th>Nama</th><th>TP</th></tr>
        <tr><td>STUDENT ALPHA</td><td><input></td></tr>
        <tr><td>STUDENT BETA</td><td><input></td></tr>
      </table>`;

    const results = await fillStudentTpRecords([
      { name: "STUDENT ALPHA", tp: 3 },
      { name: "STUDENT BETA", tp: 5 },
    ]);

    expect(results.every(result => result.filled)).toBe(true);
    expect(Array.from(document.querySelectorAll("input")).map(input => input.value)).toEqual(["", "3", "5"]);
  });

  it("uses spelling-tolerant name matches when selecting the best-fit MOEIS class table", async () => {
    document.body.innerHTML = `
      <table>
        <tr><th>Nama</th><th>TP</th></tr>
        <tr><td>OTHER STUDENT</td><td><input></td></tr>
      </table>
      <table>
        <tr><th>Nama</th><th>TP</th></tr>
        <tr><td>NIHAHARIKA BINTI ABDUL MUHAIMIN</td><td><input></td></tr>
        <tr><td>PRITISHA SREE A P JAMES</td><td><input></td></tr>
      </table>`;

    const results = await fillStudentTpRecords([
      { name: "NIHAAHARIKA BINTI ABDUL MUHAIMIN", tp: 3 },
      { name: "PRITISHAA SREE A P JAMES", tp: 5 },
    ]);

    expect(results.every(result => result.filled)).toBe(true);
    expect(Array.from(document.querySelectorAll<HTMLInputElement>("input")).map(input => input.value))
      .toEqual(["", "3", "5"]);
  });

  it("rejects a tie between equally matching MOEIS class tables without filling either", async () => {
    document.body.innerHTML = `
      <table><tr><th>Nama</th><th>TP</th></tr><tr><td>STUDENT ALPHA</td><td><input></td></tr></table>
      <table><tr><th>Nama</th><th>TP</th></tr><tr><td>STUDENT ALPHA</td><td><input></td></tr></table>`;
    await expect(fillStudentTpRecords([{ name: "STUDENT ALPHA", tp: 3 }]))
      .rejects.toThrow("Multiple MOEIS class tables match");
    expect(Array.from(document.querySelectorAll("input")).every(input => !input.value)).toBe(true);
  });

  it("recognizes the requested MOEIS PBD route and selects the proper tabs", () => {
    const source = { id: 1, url: "https://erph-pm.vercel.app/rekod-transit" };
    const target = { id: 2, url: "https://moeissppb.moe.gov.my/keputusan/pbd/pbd/20777645" };
    expect(isMoeisPbdUrl(target.url)).toBe(true);
    expect(isMoeisPbdUrl("https://moeissppb.moe.gov.my/home")).toBe(false);
    expect(findTransferTabs([source, target], 2)).toEqual({ source, target });
    expect(findTransferTabs([source, target], 1)).toEqual({ source, target });
    expect(() => findTransferTabs([source, { ...source, id: 3 }, target], 2))
      .toThrow("Multiple eRPH-PM tabs");
  });
});
