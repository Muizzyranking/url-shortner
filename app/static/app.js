const API_BASE = "/api/links";

const el = {
  form: document.getElementById("create-form"),
  targetUrl: document.getElementById("target_url"),
  slug: document.getElementById("slug"),
  expiryCustom: document.getElementById("expiry-custom"),
  expiryAmount: document.getElementById("expiry_amount"),
  expiryUnit: document.getElementById("expiry_unit"),
  presetBtns: Array.from(document.querySelectorAll(".preset-btn")),
  submitBtn: document.querySelector(".submit-btn"),
  banner: document.getElementById("banner"),
  table: document.getElementById("routes-table"),
  body: document.getElementById("routes-body"),
  empty: document.getElementById("empty-state"),
  loading: document.getElementById("loading-state"),
};

const FIELD_INPUTS = {
  target_url: el.targetUrl,
  slug: el.slug,
  expire_after: el.expiryAmount,
  expires_at: el.expiryAmount,
};

let selectedPresetSeconds = ""; // "" = never, "custom" = use amount+unit, else a number-as-string
const detailCache = new Map(); // slug -> detail payload, cleared on any list refresh

// ---------------- banner (page-level / network errors) ----------------

function showBanner(message, { error = false, html = null } = {}) {
  el.banner.hidden = false;
  el.banner.classList.toggle("error", error);
  el.banner.innerHTML = html !== null ? html : `<span>${escapeHtml(message)}</span>`;
}

function hideBanner() {
  el.banner.hidden = true;
}

// ---------------- field-level errors ----------------

function clearFieldErrors() {
  for (const key of Object.keys(FIELD_INPUTS)) {
    const input = FIELD_INPUTS[key];
    if (!input) continue;
    input.closest(".field")?.classList.remove("has-error");
  }
  document.querySelectorAll(".field-error").forEach((p) => (p.textContent = ""));
}

function setFieldError(key, message) {
  const idMap = { target_url: "err-target_url", slug: "err-slug", expire_after: "err-expiry", expires_at: "err-expiry" };
  const errEl = document.getElementById(idMap[key]);
  const input = FIELD_INPUTS[key];
  if (errEl) errEl.textContent = message;
  input?.closest(".field")?.classList.add("has-error");
}

// ---------------- helpers ----------------

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.textContent;
}

function formatDate(iso) {
  if (!iso) return "\u2014";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" }) +
    " " + d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function formatRelative(iso) {
  if (!iso) return "never";
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

function isExpired(iso) {
  if (!iso) return false;
  return new Date(iso).getTime() <= Date.now();
}

function isValidHttpUrl(value) {
  try {
    const u = new URL(value);
    return u.protocol === "http:" || u.protocol === "https:";
  } catch (_) {
    return false;
  }
}

const SLUG_PATTERN = /^[A-Za-z0-9_-]+$/;

async function apiRequest(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  let body = null;
  try {
    body = await res.json();
  } catch (_) {
    // no body (e.g. 204)
  }
  if (!res.ok) {
    const err = new Error((body && body.detail) || `request failed (${res.status})`);
    err.status = res.status;
    err.fieldErrors = (body && body.errors) || null;
    throw err;
  }
  return body;
}

// ---------------- expiry presets ----------------

el.presetBtns.forEach((btn) => {
  btn.addEventListener("click", () => {
    el.presetBtns.forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    selectedPresetSeconds = btn.dataset.seconds;
    el.expiryCustom.hidden = selectedPresetSeconds !== "custom";
  });
});

function computeExpireAfterSeconds() {
  if (selectedPresetSeconds === "" ) return null; // never
  if (selectedPresetSeconds === "custom") {
    const amount = Number(el.expiryAmount.value);
    const unitSeconds = Number(el.expiryUnit.value);
    if (!amount || amount <= 0) return { error: "enter how long until this link expires" };
    return { value: Math.round(amount * unitSeconds) };
  }
  return { value: Number(selectedPresetSeconds) };
}

// ---------------- loading + rendering the list ----------------

async function loadLinks() {
  el.loading.hidden = false;
  el.table.hidden = true;
  el.empty.hidden = true;
  try {
    const data = await apiRequest(API_BASE);
    detailCache.clear();
    renderLinks(data.links);
  } catch (err) {
    showBanner(`couldn't load routes: ${err.message}`, { error: true });
  } finally {
    el.loading.hidden = true;
  }
}

function renderLinks(links) {
  el.body.innerHTML = "";

  if (links.length === 0) {
    el.empty.hidden = false;
    el.table.hidden = true;
    return;
  }

  el.empty.hidden = true;
  el.table.hidden = false;

  for (const link of links) {
    el.body.appendChild(buildRouteRow(link));
    el.body.appendChild(buildDetailRow(link.slug));
  }
}

function buildRouteRow(link) {
  const tr = document.createElement("tr");
  tr.className = "route-row";
  tr.dataset.slug = link.slug;

  const expired = isExpired(link.expires_at);

  tr.innerHTML = `
    <td class="col-slug"><button class="slug-btn" type="button">/${escapeHtml(link.slug)}</button></td>
    <td class="col-target" data-label="to" title="${escapeHtml(link.target_url)}">${escapeHtml(link.target_url)}</td>
    <td class="col-clicks" data-label="clicks">${link.click_count}</td>
    <td class="col-created" data-label="created">${formatDate(link.created_at)}</td>
    <td class="col-expires ${expired ? "expired-tag" : ""}" data-label="expires">${
      link.expires_at ? (expired ? "expired" : formatDate(link.expires_at)) : "\u2014"
    }</td>
    <td class="col-actions">
      <button class="copy-btn" type="button">copy</button>
      <button class="delete-btn" type="button">delete</button>
    </td>
  `;

  tr.addEventListener("click", () => toggleDetail(link.slug));
  tr.querySelector(".copy-btn").addEventListener("click", (e) => {
    e.stopPropagation();
    copyShortUrl(link);
  });
  tr.querySelector(".delete-btn").addEventListener("click", (e) => {
    e.stopPropagation();
    handleDelete(link.slug);
  });

  return tr;
}

function buildDetailRow(slug) {
  const tr = document.createElement("tr");
  tr.className = "detail-row";
  tr.dataset.slugDetail = slug;
  tr.hidden = true;
  tr.innerHTML = `<td colspan="6"><div class="detail-panel"><p class="detail-loading">loading traffic\u2026</p></div></td>`;
  return tr;
}

function cssEscape(str) {
  return window.CSS && CSS.escape ? CSS.escape(str) : str;
}

async function toggleDetail(slug) {
  const row = el.body.querySelector(`tr.detail-row[data-slug-detail="${cssEscape(slug)}"]`);
  if (!row) return;

  if (!row.hidden) {
    row.hidden = true;
    return;
  }

  row.hidden = false;
  const panel = row.querySelector(".detail-panel");

  if (detailCache.has(slug)) {
    renderDetailPanel(panel, detailCache.get(slug));
    return;
  }

  try {
    const data = await apiRequest(`${API_BASE}/${encodeURIComponent(slug)}`);
    detailCache.set(slug, data);
    renderDetailPanel(panel, data);
  } catch (err) {
    panel.innerHTML = `<p class="detail-loading error">couldn't load traffic: ${escapeHtml(err.message)}</p>`;
  }
}

function renderDetailPanel(panel, data) {
  const maxCount = Math.max(1, ...data.daily_clicks.map((d) => d.count));

  const bars = data.daily_clicks
    .map((d) => {
      const heightPct = Math.round((d.count / maxCount) * 100);
      const label = new Date(d.date).toLocaleDateString(undefined, { month: "short", day: "numeric" });
      return `<div class="spark-bar" data-count="${d.count}" style="height:${Math.max(heightPct, 3)}%" title="${label}: ${d.count} click${d.count === 1 ? "" : "s"}"></div>`;
    })
    .join("");

  panel.innerHTML = `
    <div class="detail-stats">
      <div class="stat"><span class="stat-num">${data.click_count}</span><span class="stat-label">total clicks</span></div>
      <div class="stat"><span class="stat-num">${data.clicks_last_24h}</span><span class="stat-label">last 24h</span></div>
      <div class="stat"><span class="stat-num">${data.clicks_last_7d}</span><span class="stat-label">last 7d</span></div>
      <div class="stat"><span class="stat-num">${data.unique_visitors}</span><span class="stat-label">unique visitors</span></div>
    </div>
    <p class="detail-meta">last click: ${formatRelative(data.last_clicked_at)}</p>
    <div class="sparkline">${bars}</div>
    <div class="sparkline-caption">last ${data.daily_clicks.length} days</div>
  `;
}

async function copyShortUrl(link) {
  try {
    await navigator.clipboard.writeText(link.short_url);
    showBanner(`copied ${link.short_url}`);
    setTimeout(hideBanner, 2500);
  } catch (_) {
    showBanner(`short url: ${link.short_url}`);
  }
}

async function handleDelete(slug) {
  if (!confirm(`Delete /${slug}? This can't be undone.`)) return;
  try {
    await apiRequest(`${API_BASE}/${encodeURIComponent(slug)}`, { method: "DELETE" });
    showBanner(`deleted /${slug}`);
    setTimeout(hideBanner, 2000);
    await loadLinks();
  } catch (err) {
    showBanner(`couldn't delete /${slug}: ${err.message}`, { error: true });
  }
}

// ---------------- create form ----------------

function validateClientSide(payload) {
  const errors = {};

  if (!payload.target_url) {
    errors.target_url = "enter a destination URL";
  } else if (!isValidHttpUrl(payload.target_url)) {
    errors.target_url = "must be a valid http(s) URL";
  }

  if (payload.slug) {
    if (payload.slug.length < 3) {
      errors.slug = "slug must be at least 3 characters";
    } else if (!SLUG_PATTERN.test(payload.slug)) {
      errors.slug = "only letters, numbers, hyphens, and underscores";
    }
  }

  return errors;
}

el.form.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideBanner();
  clearFieldErrors();

  const payload = {
    target_url: el.targetUrl.value.trim(),
  };
  if (el.slug.value.trim()) payload.slug = el.slug.value.trim();

  const expiry = computeExpireAfterSeconds();
  if (expiry && expiry.error) {
    setFieldError("expire_after", expiry.error);
    return;
  }
  if (expiry && expiry.value) {
    payload.expire_after = expiry.value;
  }

  const clientErrors = validateClientSide(payload);
  if (Object.keys(clientErrors).length > 0) {
    for (const [field, message] of Object.entries(clientErrors)) {
      setFieldError(field, message);
    }
    return;
  }

  el.submitBtn.disabled = true;
  el.submitBtn.textContent = "Creating\u2026";

  try {
    const link = await apiRequest(API_BASE, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    resetForm();
    showBanner("", {
      html: `<span>created \u2192 <strong>${escapeHtml(link.short_url)}</strong></span>
             <button type="button" id="banner-copy">copy</button>`,
    });
    document.getElementById("banner-copy").addEventListener("click", () => copyShortUrl(link));
    await loadLinks();
  } catch (err) {
    if (err.fieldErrors && err.fieldErrors.length > 0) {
      for (const fe of err.fieldErrors) {
        setFieldError(fe.field, fe.message);
      }
    } else {
      showBanner(err.message, { error: true });
    }
  } finally {
    el.submitBtn.disabled = false;
    el.submitBtn.textContent = "Create hop";
  }
});

function resetForm() {
  el.form.reset();
  el.presetBtns.forEach((b) => b.classList.remove("active"));
  el.presetBtns[0].classList.add("active");
  selectedPresetSeconds = "";
  el.expiryCustom.hidden = true;
  clearFieldErrors();
}

loadLinks();
