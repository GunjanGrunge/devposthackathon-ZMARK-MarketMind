import React, { useState } from "react";
import { Play } from "lucide-react";

export function ClarificationForm({ form, onSubmit }) {
  const initial = Object.fromEntries(
    form.fields.map((f) => [f.id, f.default || (f.options?.[0]?.value ?? "")])
  );
  const [values, setValues] = useState(initial);

  function handleChange(fieldId, value) {
    setValues((prev) => ({ ...prev, [fieldId]: value }));
  }

  function handleSubmit(e) {
    e.preventDefault();
    const encoded = Object.entries(values)
      .map(([k, v]) => `${k}=${v}`)
      .join(", ");
    onSubmit(encoded);
  }

  return (
    <form className="clarification-form" onSubmit={handleSubmit}>
      <div className="clarification-fields">
        {form.fields.map((field) => (
          <div key={field.id} className="clarification-field">
            <label className="clarification-label">{field.label}</label>
            {field.type === "select" && field.options ? (
              <div className="clarification-chips">
                {field.options.map((opt) => (
                  <button
                    type="button"
                    key={opt.value}
                    className={`clarification-chip ${values[field.id] === opt.value ? "active" : ""}`}
                    onClick={() => handleChange(field.id, opt.value)}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            ) : (
              <input
                type="text"
                className="clarification-input"
                value={values[field.id]}
                onChange={(e) => handleChange(field.id, e.target.value)}
              />
            )}
          </div>
        ))}
      </div>
      <button type="submit" className="clarification-submit">
        <Play size={13} />
        {form.submit_label || "Run Analysis"}
      </button>
    </form>
  );
}
