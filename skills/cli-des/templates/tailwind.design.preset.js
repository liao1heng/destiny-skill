module.exports = {
  theme: {
    extend: {
      colors: {
        canvas: "var(--bg-canvas)",
        elevated: "var(--bg-elevated)",
        surface: {
          primary: "var(--surface-primary)",
          secondary: "var(--surface-secondary)",
        },
        text: {
          DEFAULT: "var(--text-default)",
          muted: "var(--text-muted)",
          inverse: "var(--text-inverse)",
        },
        accent: {
          primary: "var(--accent-primary)",
          secondary: "var(--accent-secondary)",
        },
        border: {
          soft: "var(--border-soft)",
          strong: "var(--border-strong)",
        },
      },
      fontFamily: {
        display: ["var(--font-display)"],
        body: ["var(--font-body)"],
        mono: ["var(--font-mono)"],
      },
      borderRadius: {
        sm: "var(--radius-small)",
        DEFAULT: "var(--radius-medium)",
        lg: "var(--radius-large)",
      },
      boxShadow: {
        soft: "var(--shadow-soft)",
        focus: "var(--shadow-focus)",
      },
      transitionDuration: {
        micro: "var(--motion-duration-micro)",
        standard: "var(--motion-duration-standard)",
        section: "var(--motion-duration-section)",
      },
      transitionTimingFunction: {
        enter: "var(--motion-ease-enter)",
        exit: "var(--motion-ease-exit)",
        standard: "var(--motion-ease-standard)",
      },
    },
  },
};
