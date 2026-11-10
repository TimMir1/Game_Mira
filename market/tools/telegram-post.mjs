// Публикует в Telegram-канал объявления, которые появились в market/data.js
// в последнем коммите. Запускается GitHub Actions (см. .github/workflows/telegram.yml).
//
// Переменные окружения:
//   TELEGRAM_BOT_TOKEN — токен бота от @BotFather (секрет репозитория)
//   TELEGRAM_CHAT_ID   — @имя_канала или числовой id (секрет репозитория)
//   SITE_URL           — адрес сайта, например https://user.github.io/repo/market/
//   OLD_DATA           — путь к прошлой версии data.js (может отсутствовать)
//   NEW_DATA           — путь к текущей версии data.js
import fs from "node:fs";
import vm from "node:vm";

const { TELEGRAM_BOT_TOKEN: token, TELEGRAM_CHAT_ID: chat, SITE_URL = "", OLD_DATA, NEW_DATA = "market/data.js" } = process.env;
if (!token || !chat) { console.log("Секреты TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID не заданы — пропускаю."); process.exit(0); }

function load(path) {
  if (!path || !fs.existsSync(path)) return [];
  const ctx = { window: {} };
  vm.runInNewContext(fs.readFileSync(path, "utf8"), ctx, { timeout: 2000 });
  return Array.isArray(ctx.window.LISTINGS) ? ctx.window.LISTINGS : [];
}

const oldIds = new Set(load(OLD_DATA).map(x => x.id));
const fresh = load(NEW_DATA).filter(x => !oldIds.has(x.id));
console.log(`Новых объявлений: ${fresh.length}`);

const esc = s => String(s ?? "").replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
const money = n => Number(n || 0).toLocaleString("ru-RU") + " ₽";
const base = SITE_URL.replace(/\/?$/, "/");

function caption(x) {
  const specs = Object.entries(x.specs || {}).slice(0, 5).map(([k, v]) => `• ${esc(k)}: ${esc(v)}`).join("\n");
  let desc = esc(x.description || "");
  let text = `<b>${esc(x.title)}</b>\n💰 <b>${money(x.price)}</b>${x.city ? `\n📍 ${esc(x.city)}` : ""}\n\n${desc}${specs ? "\n\n" + specs : ""}`;
  const link = SITE_URL ? `\n\n👉 <a href="${base}#/item/${encodeURIComponent(x.id)}">Открыть объявление</a>` : "";
  if (text.length + link.length > 1000) text = text.slice(0, 1000 - link.length - 1).replace(/&[a-z]*$/, "") + "…";
  return text + link;
}

function photoBlob(src) {
  const m = /^data:(image\/[\w+.-]+);base64,(.+)$/.exec(src || "");
  if (m) return new Blob([Buffer.from(m[2], "base64")], { type: m[1] });
  const local = `market/${src}`;
  if (src && !/^https?:/.test(src) && fs.existsSync(local)) return new Blob([fs.readFileSync(local)]);
  return null;
}

async function call(method, form) {
  const r = await fetch(`https://api.telegram.org/bot${token}/${method}`, { method: "POST", body: form });
  const j = await r.json();
  if (!j.ok) throw new Error(`${method}: ${j.description}`);
}

let failed = 0;
for (const x of fresh) {
  try {
    const photos = (x.photos || []).slice(0, 10);
    const form = new FormData();
    form.append("chat_id", chat);
    if (photos.length > 1) {
      const media = photos.map((p, i) => {
        const b = photoBlob(p);
        if (b) form.append(`p${i}`, b, `p${i}.jpg`);
        return { type: "photo", media: b ? `attach://p${i}` : p, ...(i === 0 ? { caption: caption(x), parse_mode: "HTML" } : {}) };
      });
      form.append("media", JSON.stringify(media));
      await call("sendMediaGroup", form);
    } else if (photos.length === 1) {
      const b = photoBlob(photos[0]);
      b ? form.append("photo", b, "photo.jpg") : form.append("photo", photos[0]);
      form.append("caption", caption(x)); form.append("parse_mode", "HTML");
      await call("sendPhoto", form);
    } else {
      form.append("text", caption(x)); form.append("parse_mode", "HTML");
      await call("sendMessage", form);
    }
    console.log(`✓ ${x.title}`);
    await new Promise(r => setTimeout(r, 1500)); // не упираться в лимиты Telegram
  } catch (e) { failed++; console.error(`✗ ${x.title}: ${e.message}`); }
}
if (failed) process.exit(1);
