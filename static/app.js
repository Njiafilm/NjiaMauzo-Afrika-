from pathlib import Path

app_js = r"""/*
 * NjiaMauzo Afrika - Frontend Application
 * app.js
 *
 * Drop-in frontend JavaScript for the NjiaMauzo web app.
 * Works with normal HTML pages and a Flask/REST backend.
 */

(() => {
  "use strict";

  const API_BASE =
    document.documentElement.dataset.apiBase ||
    window.NJIAMAUZO_API_BASE ||
    "";

  const APP_NAME = "NjiaMauzo Afrika";

  // ---------- Small utilities ----------

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

  const escapeHtml = (value) => {
    const div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
  };

  const formatMoney = (amount, currency = "TZS") => {
    const n = Number(amount);
    if (!Number.isFinite(n)) return `${escapeHtml(currency)} 0`;
    try {
      return new Intl.NumberFormat("sw-TZ", {
        style: "currency",
        currency,
        maximumFractionDigits: 0
      }).format(n);
    } catch {
      return `${currency} ${Math.round(n).toLocaleString()}`;
    }
  };

  const getJson = (key, fallback = null) => {
    try {
      const value = localStorage.getItem(key);
      return value === null ? fallback : JSON.parse(value);
    } catch {
      return fallback;
    }
  };

  const setJson = (key, value) => {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (e) {
      console.warn("Local storage unavailable:", e);
    }
  };

  const getToken = () =>
    localStorage.getItem("njiamauzo_token") ||
    sessionStorage.getItem("njiamauzo_token") ||
    "";

  const getUser = () =>
    getJson("njiamauzo_user", null) ||
    getJson("user", null);

  const setUser = (user) => {
    if (user) {
      setJson("njiamauzo_user", user);
      setJson("user", user);
    } else {
      localStorage.removeItem("njiamauzo_user");
      localStorage.removeItem("user");
    }
  };

  const showToast = (message, type = "info") => {
    let box = $("#njiamauzo-toast-container");

    if (!box) {
      box = document.createElement("div");
      box.id = "njiamauzo-toast-container";
      box.style.cssText = `
        position:fixed;right:18px;bottom:18px;z-index:99999;
        display:flex;flex-direction:column;gap:10px;
        max-width:min(92vw,420px);
      `;
      document.body.appendChild(box);
    }

    const toast = document.createElement("div");
    toast.setAttribute("role", "alert");
    toast.style.cssText = `
      padding:13px 16px;border-radius:12px;
      color:#fff;font:500 14px/1.45 system-ui,sans-serif;
      box-shadow:0 8px 30px rgba(0,0,0,.20);
      background:${type === "success" ? "#16803c" :
                   type === "error" ? "#b42318" :
                   type === "warning" ? "#a15c00" : "#175cd3"};
    `;
    toast.textContent = message;
    box.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(8px)";
      toast.style.transition = "all .25s ease";
      setTimeout(() => toast.remove(), 300);
    }, 3200);
  };

  window.showToast = showToast;

  const setLoading = (button, loading, text = "Inapakia...") => {
    if (!button) return;
    if (loading) {
      button.dataset.originalText = button.innerHTML;
      button.disabled = true;
      button.innerHTML = text;
      button.setAttribute("aria-busy", "true");
    } else {
      button.disabled = false;
      button.innerHTML =
        button.dataset.originalText || button.innerHTML;
      button.removeAttribute("aria-busy");
    }
  };

  // ---------- API ----------

  async function api(path, options = {}) {
    const url =
      path.startsWith("http://") || path.startsWith("https://")
        ? path
        : `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;

    const headers = {
      Accept: "application/json",
      ...(options.body && !(options.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...(options.headers || {})
    };

    const token = getToken();
    if (token && !headers.Authorization) {
      headers.Authorization = `Bearer ${token}`;
    }

    const response = await fetch(url, {
      ...options,
      headers,
      credentials: "include"
    });

    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json")
      ? await response.json().catch(() => ({}))
      : await response.text();

    if (!response.ok) {
      const message =
        typeof data === "object"
          ? data.message || data.error || data.detail
          : data;
      throw new Error(message || `HTTP ${response.status}`);
    }

    return data;
  }

  window.njiaMauzoAPI = api;

  // ---------- Authentication ----------

  async function login(email, password, remember = true) {
    const data = await api("/api/login", {
      method: "POST",
      body: JSON.stringify({ email, password })
    });

    const token =
      data.token ||
      data.access_token ||
      data.accessToken ||
      data.data?.token;

    const user = data.user || data.data?.user || data.account;

    if (token) {
      const store = remember ? localStorage : sessionStorage;
      store.setItem("njiamauzo_token", token);
    }

    if (user) setUser(user);

    return data;
  }

  async function register(payload) {
    const data = await api("/api/register", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    const token =
      data.token ||
      data.access_token ||
      data.accessToken ||
      data.data?.token;

    if (token) localStorage.setItem("njiamauzo_token", token);

    if (data.user || data.data?.user) {
      setUser(data.user || data.data.user);
    }

    return data;
  }

  function logout() {
    localStorage.removeItem("njiamauzo_token");
    sessionStorage.removeItem("njiamauzo_token");
    localStorage.removeItem("njiamauzo_user");
    localStorage.removeItem("user");
    window.location.href = "/";
  }

  window.njiaMauzo = {
    api,
    login,
    register,
    logout,
    getUser,
    showToast,
    formatMoney
  };

  // ---------- Product rendering ----------

  const productImage = (product) =>
    product.image ||
    product.image_url ||
    product.photo ||
    "/static/img/product-placeholder.png";

  function productCard(product) {
    const id = product.id ?? product.product_id ?? "";
    const name = product.name || product.title || "Bidhaa";
    const price = product.price ?? product.amount ?? 0;
    const currency = product.currency || "TZS";
    const location = product.location || product.city || product.region || "";
    const seller = product.seller_name || product.seller || "";

    return `
      <article class="product-card" data-product-id="${escapeHtml(id)}">
        <a class="product-card__link" href="/product/${encodeURIComponent(id)}">
          <img
            class="product-card__image"
            src="${escapeHtml(productImage(product))}"
            alt="${escapeHtml(name)}"
            loading="lazy"
            onerror="this.src='/static/img/product-placeholder.png'"
          >
          <div class="product-card__body">
            <h3 class="product-card__title">${escapeHtml(name)}</h3>
            <div class="product-card__price">${formatMoney(price, currency)}</div>
            ${location ? `<div class="product-card__location">📍 ${escapeHtml(location)}</div>` : ""}
            ${seller ? `<div class="product-card__seller">${escapeHtml(seller)}</div>` : ""}
          </div>
        </a>
      </article>
    `;
  }

  function renderProducts(products, container) {
    if (!container) return;

    if (!Array.isArray(products) || products.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <strong>Hakuna bidhaa zilizopatikana.</strong>
          <p>Jaribu kutafuta kwa jina jingine au badilisha eneo.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = products.map(productCard).join("");
  }

  window.renderProducts = renderProducts;

  // ---------- Search ----------

  async function searchProducts(query = "", extra = {}) {
    const params = new URLSearchParams();

    if (query) params.set("q", query.trim());

    Object.entries(extra).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        params.set(key, value);
      }
    });

    const endpoints = [
      `/api/products?${params.toString()}`,
      `/api/search?${params.toString()}`
    ];

    let lastError;

    for (const endpoint of endpoints) {
      try {
        const data = await api(endpoint);
        return data.products || data.items || data.results || data.data || data;
      } catch (error) {
        lastError = error;
      }
    }

    throw lastError || new Error("Search failed");
  }

  async function handleSearch(event) {
    event.preventDefault();

    const form = event.currentTarget;
    const input =
      $('input[name="q"]', form) ||
      $('input[type="search"]', form);

    const button = $("button[type='submit']", form);
    const container =
      document.querySelector("[data-products]") ||
      document.querySelector("#products-grid") ||
      document.querySelector(".products-grid");

    const query = input?.value || "";

    setLoading(button, true, "Inatafuta...");

    try {
      const products = await searchProducts(query);
      renderProducts(products, container);

      const url = new URL(window.location.href);
      if (query) url.searchParams.set("q", query);
      else url.searchParams.delete("q");
      history.replaceState({}, "", url);

      showToast(`${Array.isArray(products) ? products.length : 0} bidhaa zimepatikana.`, "success");
    } catch (error) {
      console.error(error);
      showToast("Imeshindikana kutafuta bidhaa. Jaribu tena.", "error");
    } finally {
      setLoading(button, false);
    }
  }

  // ---------- Payment / assisted market search ----------

  async function requestAssistedSearch() {
    const user = getUser();

    if (!user) {
      showToast("Tafadhali ingia kwanza ili kutumia huduma ya kutafutiwa masoko.", "warning");
      window.location.href = "/login";
      return;
    }

    try {
      const result = await api("/api/assisted-search/request", {
        method: "POST",
        body: JSON.stringify({})
      });

      if (result.payment_required || result.status === "payment_required") {
        openPaymentDialog(result);
        return result;
      }

      showToast("Ombi lako limepokelewa.", "success");
      return result;
    } catch (error) {
      console.error(error);
      showToast(error.message || "Imeshindikana kutuma ombi.", "error");
      throw error;
    }
  }

  function openPaymentDialog(data = {}) {
    const old = $("#payment-dialog");
    if (old) old.remove();

    const amount = data.amount || data.price || 1000;
    const currency = data.currency || "TZS";

    const modal = document.createElement("div");
    modal.id = "payment-dialog";
    modal.style.cssText = `
      position:fixed;inset:0;background:rgba(0,0,0,.65);
      z-index:99990;display:grid;place-items:center;padding:18px;
    `;

    modal.innerHTML = `
      <div style="
        width:min(100%,460px);background:#fff;border-radius:18px;
        padding:24px;box-shadow:0 20px 60px rgba(0,0,0,.3);
        font-family:system-ui,sans-serif;
      ">
        <button type="button" data-close-payment
          style="float:right;border:0;background:none;font-size:26px;cursor:pointer">×</button>

        <h2 style="margin:0 0 8px">Tafuta Soko & Bidhaa</h2>
        <p style="color:#555">
          Huduma ya kusaidiwa kutafuta masoko na bidhaa inahitaji malipo
          yaliyothibitishwa.
        </p>

        <div style="
          margin:18px 0;padding:16px;border-radius:12px;
          background:#f5f7fa;font-size:22px;font-weight:700;
        ">${formatMoney(amount, currency)}</div>

        <button type="button" id="start-payment"
          style="
            width:100%;padding:13px;border:0;border-radius:10px;
            background:#16803c;color:#fff;font-weight:700;cursor:pointer
          ">
          Endelea na Malipo
        </button>
      </div>
    `;

    document.body.appendChild(modal);

    $("[data-close-payment]", modal)?.addEventListener("click", () => modal.remove());

    $("#start-payment", modal)?.addEventListener("click", async (event) => {
      const button = event.currentTarget;
      setLoading(button, true, "Inaandaa malipo...");

      try {
        const result = await api("/api/payments/create", {
          method: "POST",
          body: JSON.stringify({
            amount,
            currency,
            service: "assisted_search"
          })
        });

        if (result.checkout_url || result.payment_url || result.url) {
          window.location.href =
            result.checkout_url || result.payment_url || result.url;
          return;
        }

        showToast(
          result.message || "Malipo yameanzishwa. Fuata maelekezo ya mfumo.",
          "success"
        );
        modal.remove();
      } catch (error) {
        console.error(error);
        showToast(error.message || "Malipo hayajaanzishwa.", "error");
        setLoading(button, false);
      }
    });
  }

  window.requestAssistedSearch = requestAssistedSearch;

  // ---------- Forms ----------

  function bindLoginForm(form) {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();

      const email =
        form.querySelector('[name="email"]')?.value.trim() || "";
      const password =
        form.querySelector('[name="password"]')?.value || "";
      const remember =
        form.querySelector('[name="remember"]')?.checked ?? true;
      const button = form.querySelector('[type="submit"]');

      if (!email || !password) {
        showToast("Jaza barua pepe na password.", "warning");
        return;
      }

      setLoading(button, true, "Inaingia...");

      try {
        await login(email, password, remember);
        showToast("Umeingia kikamilifu.", "success");
        window.location.href = form.dataset.successUrl || "/dashboard";
      } catch (error) {
        console.error(error);
        showToast(error.message || "Email au password si sahihi.", "error");
      } finally {
        setLoading(button, false);
      }
    });
  }

  function bindRegisterForm(form) {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();

      const formData = new FormData(form);
      const payload = Object.fromEntries(formData.entries());

      if (payload.password !== payload.confirm_password) {
        showToast("Password hazifanani.", "warning");
        return;
      }

      const button = form.querySelector('[type="submit"]');
      setLoading(button, true, "Inafungua akaunti...");

      try {
        await register(payload);
        showToast("Akaunti imefunguliwa.", "success");
        window.location.href = form.dataset.successUrl || "/dashboard";
      } catch (error) {
        console.error(error);
        showToast(error.message || "Imeshindikana kufungua akaunti.", "error");
      } finally {
        setLoading(button, false);
      }
    });
  }

  // ---------- Navigation / UI ----------

  function bindNavigation() {
    $$("[data-logout], .logout-btn, [href='/logout']").forEach((el) => {
      el.addEventListener("click", (event) => {
        event.preventDefault();
        logout();
      });
    });

    $$("[data-assisted-search], .assisted-search-btn").forEach((el) => {
      el.addEventListener("click", (event) => {
        event.preventDefault();
        requestAssistedSearch();
      });
    });

    $$("[data-menu-toggle], .menu-toggle").forEach((button) => {
      button.addEventListener("click", () => {
        const targetSelector = button.dataset.target || ".mobile-menu";
        const menu = document.querySelector(targetSelector);
        if (menu) menu.classList.toggle("open");
      });
    });
  }

  async function loadInitialProducts() {
    const container =
      document.querySelector("[data-products]") ||
      document.querySelector("#products-grid") ||
      document.querySelector(".products-grid");

    if (!container) return;

    const url = new URL(window.location.href);
    const q = url.searchParams.get("q") || "";

    try {
      const products = await searchProducts(q);
      renderProducts(products, container);
    } catch (error) {
      console.warn("Could not load products:", error);
      // Do not break the page if the backend endpoint is unavailable.
    }
  }

  function fillUserUI() {
    const user = getUser();
    if (!user) return;

    $$("[data-user-name], .user-name").forEach((el) => {
      el.textContent =
        user.name ||
        user.full_name ||
        user.username ||
        user.email ||
        "Mtumiaji";
    });

    $$("[data-user-email], .user-email").forEach((el) => {
      el.textContent = user.email || "";
    });

    $$("[data-auth-only]").forEach((el) => {
      el.hidden = false;
    });
  }

  // ---------- Start application ----------

  document.addEventListener("DOMContentLoaded", () => {
    $$("form[data-search-form], .search-form").forEach((form) => {
      form.addEventListener("submit", handleSearch);
    });

    $$("form[data-login-form], #login-form").forEach(bindLoginForm);
    $$("form[data-register-form], #register-form").forEach(bindRegisterForm);

    bindNavigation();
    fillUserUI();
    loadInitialProducts();

    // Keep buttons from submitting accidentally when marked as UI-only.
    $$("[data-action='prevent-submit']").forEach((button) => {
      button.addEventListener("click", (event) => event.preventDefault());
    });

    console.log(`${APP_NAME} app.js loaded successfully.`);
  });
})();
"""

path = Path("/mnt/data/app.js")
path.write_text(app_js, encoding="utf-8")

print(f"Created: {path}")
print(f"Size: {path.stat().st_size:,} bytes")
