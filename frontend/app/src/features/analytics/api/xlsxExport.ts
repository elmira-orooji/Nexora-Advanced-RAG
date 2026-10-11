type CellValue = string | number | null | undefined;

interface Worksheet {
  name: string;
  rows: CellValue[][];
}

const encoder = new TextEncoder();

function escapeXml(value: string) {
  return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&apos;");
}

function columnName(index: number) {
  let value = index + 1;
  let name = "";
  while (value > 0) { const remainder = (value - 1) % 26; name = String.fromCharCode(65 + remainder) + name; value = Math.floor((value - 1) / 26); }
  return name;
}

function worksheetXml(rows: CellValue[][]) {
  const body = rows.map((row, rowIndex) => {
    const cells = row.map((value, columnIndex) => {
      if (value === null || value === undefined) return "";
      const reference = `${columnName(columnIndex)}${rowIndex + 1}`;
      if (typeof value === "number" && Number.isFinite(value)) return `<c r="${reference}" t="n"><v>${value}</v></c>`;
      return `<c r="${reference}" t="inlineStr"><is><t xml:space="preserve">${escapeXml(String(value))}</t></is></c>`;
    }).join("");
    return `<row r="${rowIndex + 1}">${cells}</row>`;
  }).join("");
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>${body}</sheetData></worksheet>`;
}

function u16(value: number) { return new Uint8Array([value & 0xff, value >>> 8 & 0xff]); }
function u32(value: number) { return new Uint8Array([value & 0xff, value >>> 8 & 0xff, value >>> 16 & 0xff, value >>> 24 & 0xff]); }
function join(parts: Uint8Array[]) { const size = parts.reduce((total, part) => total + part.length, 0); const output = new Uint8Array(size); let offset = 0; parts.forEach((part) => { output.set(part, offset); offset += part.length; }); return output; }

function crc32(bytes: Uint8Array) {
  let value = 0xffffffff;
  for (const byte of bytes) { value ^= byte; for (let bit = 0; bit < 8; bit += 1) value = value & 1 ? value >>> 1 ^ 0xedb88320 : value >>> 1; }
  return (value ^ 0xffffffff) >>> 0;
}

function zip(entries: Array<{ name: string; content: string }>) {
  let offset = 0;
  const local: Uint8Array[] = [];
  const central: Uint8Array[] = [];
  for (const entry of entries) {
    const name = encoder.encode(entry.name);
    const content = encoder.encode(entry.content);
    const checksum = crc32(content);
    const localHeader = join([u32(0x04034b50), u16(20), u16(0), u16(0), u16(0), u16(0), u32(checksum), u32(content.length), u32(content.length), u16(name.length), u16(0), name, content]);
    local.push(localHeader);
    central.push(join([u32(0x02014b50), u16(20), u16(20), u16(0), u16(0), u16(0), u16(0), u32(checksum), u32(content.length), u32(content.length), u16(name.length), u16(0), u16(0), u16(0), u16(0), u32(0), u32(offset), name]));
    offset += localHeader.length;
  }
  const centralDirectory = join(central);
  return join([...local, centralDirectory, u32(0x06054b50), u16(0), u16(0), u16(entries.length), u16(entries.length), u32(centralDirectory.length), u32(offset), u16(0)]);
}

export function createXlsxWorkbook(sheets: Worksheet[]) {
  const sheetXml = sheets.map((sheet) => worksheetXml(sheet.rows));
  const contentTypes = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>${sheets.map((_, index) => `<Override PartName="/xl/worksheets/sheet${index + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join("")}</Types>`;
  const relationships = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>`;
  const workbook = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>${sheets.map((sheet, index) => `<sheet name="${escapeXml(sheet.name.slice(0, 31))}" sheetId="${index + 1}" r:id="rId${index + 1}"/>`).join("")}</sheets></workbook>`;
  const workbookRelationships = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${sheets.map((_, index) => `<Relationship Id="rId${index + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${index + 1}.xml"/>`).join("")}</Relationships>`;
  const entries = [
    { name: "[Content_Types].xml", content: contentTypes },
    { name: "_rels/.rels", content: relationships },
    { name: "xl/workbook.xml", content: workbook },
    { name: "xl/_rels/workbook.xml.rels", content: workbookRelationships },
    ...sheetXml.map((content, index) => ({ name: `xl/worksheets/sheet${index + 1}.xml`, content })),
  ];
  return new Blob([zip(entries)], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
}
