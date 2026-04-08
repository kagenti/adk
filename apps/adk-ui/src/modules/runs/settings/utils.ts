/**
 * Copyright 2026 © IBM Corp.
 * SPDX-License-Identifier: Apache-2.0
 */

import type {
  CheckboxGroupFieldValue,
  SettingsFormRender,
  SettingsFormValues,
  SingleSelectFieldValue,
} from '@kagenti/adk';
import { match } from 'ts-pattern';

export function getInitialSettingsFormValues(settingsForm: SettingsFormRender | null) {
  const fields = settingsForm?.fields ?? [];

  const defaults = fields.reduce<SettingsFormValues>((valuesAcc, field) => {
    valuesAcc[field.id] = match(field)
      .with({ type: 'checkbox_group' }, ({ fields }) => {
        const values = fields.reduce<NonNullable<CheckboxGroupFieldValue['value']>>((acc, field) => {
          acc[field.id] = field.default_value;

          return acc;
        }, {});

        return {
          type: 'checkbox_group',
          value: values,
        } satisfies CheckboxGroupFieldValue;
      })
      .with({ type: 'singleselect' }, ({ default_value }) => {
        return {
          type: 'singleselect',
          value: default_value,
        } satisfies SingleSelectFieldValue;
      })
      .exhaustive();

    return valuesAcc;
  }, {});

  return defaults;
}
