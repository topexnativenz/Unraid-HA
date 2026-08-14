/**
 * Force Pacific/Auckland (NZST/NZDT) for Flux UI dashboards.
 *
 * calendar-card-pro formats event times with Date#getHours / getDate (browser
 * local TZ). The iOS Companion app / iPhone are on NZ time, so Flux UI phone
 * looks correct. Fully Kiosk tablets often are not — this module makes the
 * tablet browser behave like that NZ device for /flux-ui* paths only.
 */
(function () {
  const TZ = "Pacific/Auckland";
  if (window.__fluxNzTimezoneInstalled) return;
  window.__fluxNzTimezoneInstalled = true;

  const OriginalDate = Date;
  const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  function onFluxUi() {
    try {
      const path = String(location.pathname || "");
      return path.includes("/flux-ui");
    } catch (e) {
      return false;
    }
  }

  function pinFully() {
    if (typeof fully === "undefined" || window.__fluxNzTzPinned) return;
    try {
      if (typeof fully.setTimezone === "function") fully.setTimezone(TZ);
      else if (typeof fully.setStringSetting === "function")
        fully.setStringSetting("timezoneId", TZ);
      window.__fluxNzTzPinned = true;
    } catch (e) {
      /* ignore */
    }
  }

  function tzParts(date) {
    const dtf = new Intl.DateTimeFormat("en-US", {
      timeZone: TZ,
      hourCycle: "h23",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      weekday: "short",
    });
    const out = {};
    for (const p of dtf.formatToParts(date)) {
      if (p.type !== "literal") out[p.type] = p.value;
    }
    return {
      year: +out.year,
      month: +out.month,
      day: +out.day,
      hour: +out.hour,
      minute: +out.minute,
      second: +out.second,
      weekday: out.weekday,
    };
  }

  function getOffsetMs(date) {
    const p = tzParts(date);
    const asUTC = OriginalDate.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second);
    return asUTC - date.getTime();
  }

  function zonedLocalToUtcMs(y, m, d, h, mi, s, ms) {
    const utcGuess = OriginalDate.UTC(y, m, d, h, mi, s, ms);
    let t = utcGuess;
    for (let i = 0; i < 2; i++) {
      const offset = getOffsetMs(new OriginalDate(t));
      t = utcGuess - offset;
    }
    return t;
  }

  function weekdayIndex(shortName) {
    const map = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };
    return map[shortName] ?? 0;
  }

  pinFully();
  setInterval(pinFully, 60000);

  const proto = OriginalDate.prototype;
  const originals = {
    getFullYear: proto.getFullYear,
    getMonth: proto.getMonth,
    getDate: proto.getDate,
    getDay: proto.getDay,
    getHours: proto.getHours,
    getMinutes: proto.getMinutes,
    getSeconds: proto.getSeconds,
    toDateString: proto.toDateString,
  };

  proto.getFullYear = function () {
    return onFluxUi() ? tzParts(this).year : originals.getFullYear.call(this);
  };
  proto.getMonth = function () {
    return onFluxUi() ? tzParts(this).month - 1 : originals.getMonth.call(this);
  };
  proto.getDate = function () {
    return onFluxUi() ? tzParts(this).day : originals.getDate.call(this);
  };
  proto.getDay = function () {
    return onFluxUi() ? weekdayIndex(tzParts(this).weekday) : originals.getDay.call(this);
  };
  proto.getHours = function () {
    return onFluxUi() ? tzParts(this).hour : originals.getHours.call(this);
  };
  proto.getMinutes = function () {
    return onFluxUi() ? tzParts(this).minute : originals.getMinutes.call(this);
  };
  proto.getSeconds = function () {
    return onFluxUi() ? tzParts(this).second : originals.getSeconds.call(this);
  };
  proto.toDateString = function () {
    if (!onFluxUi()) return originals.toDateString.call(this);
    const p = tzParts(this);
    const day = String(p.day).padStart(2, " ");
    return `${WEEKDAYS[weekdayIndex(p.weekday)]} ${MONTHS[p.month - 1]} ${day} ${p.year}`;
  };

  function FluxDate(...args) {
    if (!onFluxUi()) {
      if (args.length === 1) return new OriginalDate(args[0]);
      if (args.length === 0) return new OriginalDate();
      return new OriginalDate(...args);
    }
    if (args.length === 0) return new OriginalDate();
    if (args.length === 1) return new OriginalDate(args[0]);
    if (typeof args[0] === "number") {
      const [y, m, d = 1, h = 0, mi = 0, s = 0, ms = 0] = args;
      return new OriginalDate(zonedLocalToUtcMs(y, m, d, h, mi, s, ms));
    }
    return new OriginalDate(...args);
  }

  FluxDate.UTC = OriginalDate.UTC.bind(OriginalDate);
  FluxDate.parse = OriginalDate.parse.bind(OriginalDate);
  FluxDate.now = OriginalDate.now.bind(OriginalDate);
  FluxDate.prototype = OriginalDate.prototype;
  Object.defineProperty(FluxDate, "name", { value: "Date" });

  // Replace global Date so `new Date(y, m, d)` (all-day parsing) is NZ wall time.
  // eslint-disable-next-line no-global-assign
  Date = FluxDate;
})();
