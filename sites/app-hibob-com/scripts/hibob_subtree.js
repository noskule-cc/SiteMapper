// hibob_subtree.js — extract the full reporting subtree under a given person.
//
// WHERE THIS RUNS: inside the authenticated app.hibob.com browser tab (e.g. via the
// Chrome MCP `javascript_tool`). Unlike the connect-ggplus-ch Python scripts, HiBob's
// /api is COOKIE-authed against the logged-in session — there is no bearer token to
// store and no headless mode. You must be signed in to app.hibob.com first; this
// script never sees or handles credentials.
//
// USAGE (evaluate this file once to define the function, then call it):
//   await hibobSubtree("André Senn")                 // by name (case-insensitive; contains-match)
//   await hibobSubtree("andre.senn@gehriggroup.ch")  // by exact work email
//   await hibobSubtree("André Senn", { maxDepth: 2 })// only 2 levels below the root
//   await hibobSubtree("André Senn", { includeEmail: true })  // add emails (see note)
//
// RETURNS (ok):   { ok:true, root:{name,title,department,site},
//                   totalDescendants, directReports, tree, flat }
//   tree  = nested { name, title, department, site, directReports, reports:[...] }
//   flat  = [{ name, title, department, site, depth }, ...] (root first), handy for CSV
// RETURNS (not ok): { ok:false, error, candidates? }  // no/ambiguous match
//
// NOTE ON EMAILS: default output omits email addresses. The Chrome javascript_tool's
// safety filter BLOCKS returning payloads that contain emails/cookies, so keep
// includeEmail:false when capturing through that tool; set it true only when you can
// consume the raw return directly.

(() => {
  async function getJSON(url) {
    const r = await fetch(url, { credentials: 'include', headers: { accept: 'application/json' } });
    if (!r.ok) throw new Error(url + ' -> HTTP ' + r.status);
    return r.json();
  }

  // A metadata list is { values: [{ serverId, value, children:[...] }, ...] }.
  // Flatten (recursively, options can nest) into serverId -> human-readable value.
  function buildListMap(list) {
    const m = new Map();
    (function walk(arr) {
      if (!Array.isArray(arr)) return;
      for (const it of arr) {
        if (it && it.serverId != null) m.set(String(it.serverId), it.value);
        if (it && it.children) walk(it.children);
      }
    })(list && list.values ? list.values : []);
    return m;
  }

  globalThis.hibobSubtree = async function (rootQuery, opts = {}) {
    const maxDepth = opts.maxDepth == null ? Infinity : Number(opts.maxDepth);
    const includeEmail = !!opts.includeEmail;
    if (!rootQuery || !String(rootQuery).trim()) return { ok: false, error: 'empty rootQuery' };
    const q = String(rootQuery).trim().toLowerCase();

    // --- data ---
    const emps = await getJSON('/api/employees/essentials');           // 1 row per employee
    const lists = await getJSON('/api/company/metadata/lists/');       // option lists
    const titleMap = buildListMap(lists.title);
    const deptMap = buildListMap(lists.department);

    // --- resolve the root person: exact email > exact name > name-contains ---
    let matches = emps.filter(e => (e.email || '').toLowerCase() === q);
    if (!matches.length) {
      const exact = emps.filter(e => (e.displayName || '').toLowerCase() === q);
      matches = exact.length ? exact : emps.filter(e => (e.displayName || '').toLowerCase().includes(q));
    }
    if (matches.length === 0) return { ok: false, error: 'no employee matches "' + rootQuery + '"' };
    if (matches.length > 1) {
      return {
        ok: false,
        error: 'ambiguous root "' + rootQuery + '" (' + matches.length + ' matches)',
        candidates: matches.map(e => ({
          name: e.displayName,
          title: titleMap.get(String(e.work && e.work.title)) || null,
          site: (e.work && e.work.site) || null,
          email: includeEmail ? (e.email || null) : undefined,
        })),
      };
    }
    const root = matches[0];

    // --- index: manager id -> [report ids] ---
    const byId = new Map(emps.map(e => [e.id, e]));
    const children = new Map();
    for (const e of emps) {
      const mgr = e.work && e.work.reportsTo && e.work.reportsTo.id;
      if (mgr) {
        if (!children.has(mgr)) children.set(mgr, []);
        children.get(mgr).push(e.id);
      }
    }

    const flat = [];
    function nodeOf(id, depth) {
      const e = byId.get(id), w = e.work || {};
      const rec = {
        name: e.displayName,
        title: titleMap.get(String(w.title)) || (w.title != null ? String(w.title) : null),
        department: deptMap.get(String(w.department)) || null,
        site: w.site || null,
      };
      if (includeEmail) rec.email = e.email || null;
      flat.push({ ...rec, depth });
      const kidIds = children.get(id) || [];
      rec.directReports = kidIds.length;
      let reports = [];
      if (depth < maxDepth) {
        reports = kidIds.map(cid => nodeOf(cid, depth + 1));
        reports.sort((a, b) => (a.title || '').localeCompare(b.title || '') || a.name.localeCompare(b.name));
      }
      rec.reports = reports;
      return rec;
    }
    const tree = nodeOf(root.id, 0);

    // total descendants regardless of the maxDepth display cut
    function countAll(id) {
      return (children.get(id) || []).reduce((s, k) => s + 1 + countAll(k), 0);
    }

    return {
      ok: true,
      root: { name: root.displayName, title: tree.title, department: tree.department, site: tree.site },
      totalDescendants: countAll(root.id),
      directReports: (children.get(root.id) || []).length,
      tree,
      flat,
    };
  };

  return 'hibobSubtree() ready — call: await hibobSubtree("<name or email>")';
})();
