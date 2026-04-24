module.exports = {
  theme: {
    extend: {
      colors: {
        page: "var(--color-page-bg)",
        panel: "var(--color-panel-bg)",
        text: "var(--color-text)",
        muted: "var(--color-muted-text)",
        brand: "var(--color-brand)",
        border: "var(--color-border)",
        focus: "var(--color-focus)",
        success: "var(--color-success)",
        warning: "var(--color-warning)",
        danger: "var(--color-danger)",
        info: "var(--color-info)"
      },
      fontFamily: {
        heading: ["var(--font-heading)"],
        body: ["var(--font-body)"],
        label: ["var(--font-label)"],
        code: ["var(--font-code)"]
      },
      spacing: {
        base: "var(--space-base)",
        page: "var(--space-page-x)",
        section: "var(--space-section-y)",
        panel: "var(--space-panel-padding)",
        field: "var(--space-field-gap)"
      },
      height: {
        control: "var(--size-control-height)"
      },
      borderRadius: {
        control: "var(--radius-control)",
        panel: "var(--radius-panel)"
      },
      transitionDuration: {
        fast: "var(--motion-fast)",
        normal: "var(--motion-normal)",
        slow: "var(--motion-slow)"
      },
      transitionTimingFunction: {
        DEFAULT: "var(--motion-ease)"
      }
    }
  }
};
