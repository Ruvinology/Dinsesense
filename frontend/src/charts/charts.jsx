/**
 * Charts for the dashboard.
 *
 * Design rules applied here:
 *  - Sentiment is a diverging scale (negative <-> positive), so it uses two
 *    opposed hues with a gray midpoint, in a fixed order. Blue is positive
 *    rather than green because red/green is the worst colour-blind pair.
 *  - Every chart carries direct labels or a table, so colour is never the only
 *    way to read it.
 *  - Aspect counts are magnitude, not identity - one hue, no legend needed.
 *  - Grid and axes are recessive; the data is the loudest thing on screen.
 */

import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import { EmptyNote, prettyAspect } from '../components/ui'

const POSITIVE = '#2a78d6'
const NEUTRAL = '#8a8880'
const NEGATIVE = '#c0392b'

const axisProps = {
  stroke: 'var(--baseline)',
  tick: { fill: '#687b6e', fontSize: 11 },
  tickLine: false,
}

function TooltipBox({ title, rows }) {
  return (
    <div
      className="rounded-xl border px-3.5 py-2.5 text-xs shadow-md"
      style={{ background: '#ffffff', borderColor: 'rgba(21,36,27,0.12)' }}
    >
      <p className="mb-1 font-medium">{title}</p>
      {rows.map((row) => (
        <p key={row.label} className="flex items-center gap-2">
          <span
            className="inline-block h-2 w-2 rounded-full"
            style={{ background: row.color }}
            aria-hidden="true"
          />
          <span style={{ color: 'var(--text-secondary)' }}>{row.label}</span>
          <span className="ml-auto tabular font-medium">{row.value}</span>
        </p>
      ))}
    </div>
  )
}

/**
 * Sentiment split as one horizontal 100% bar.
 *
 * A donut was the obvious choice and the wrong one: people read angles badly,
 * and the whole question here is "how big is the negative slice compared to the
 * others". A single stacked bar answers that with length, which reads exactly.
 */
export function SentimentSplit({ counts }) {
  const total = (counts?.positive || 0) + (counts?.neutral || 0) + (counts?.negative || 0)
  if (!total) return <EmptyNote>No analysed reviews yet.</EmptyNote>

  const segments = [
    { key: 'negative', label: 'Negative', value: counts.negative, color: NEGATIVE },
    { key: 'neutral', label: 'Neutral', value: counts.neutral, color: NEUTRAL },
    { key: 'positive', label: 'Positive', value: counts.positive, color: POSITIVE },
  ]

  return (
    <div>
      <div className="flex h-9 w-full gap-[2px] overflow-hidden rounded">
        {segments.map((segment) =>
          segment.value > 0 ? (
            <div
              key={segment.key}
              className="flex items-center justify-center text-xs font-medium text-white"
              style={{ background: segment.color, width: `${(segment.value / total) * 100}%` }}
              title={`${segment.label}: ${segment.value}`}
            >
              {segment.value / total > 0.08 && (
                <span className="tabular">{Math.round((segment.value / total) * 100)}%</span>
              )}
            </div>
          ) : null,
        )}
      </div>

      <dl className="mt-4 grid grid-cols-3 gap-3">
        {segments.map((segment) => (
          <div key={segment.key}>
            <dt className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--text-secondary)' }}>
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ background: segment.color }}
                aria-hidden="true"
              />
              {segment.label}
            </dt>
            <dd className="tabular mt-0.5 text-lg font-semibold">{segment.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

/** Sentiment over time. Stacked area - the question is composition, not level. */
export function TrendChart({ data }) {
  if (!data?.length) return <EmptyNote>Not enough dated reviews to plot a trend yet.</EmptyNote>

  return (
    <div>
      <ResponsiveContainer width="100%" height={260}>
        <AreaChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
          <CartesianGrid stroke="#d9e3d6" strokeDasharray="0" vertical={false} />
          <XAxis
            dataKey="period"
            {...axisProps}
            tickFormatter={(value) => String(value).slice(5)}
            minTickGap={24}
          />
          <YAxis {...axisProps} allowDecimals={false} width={40} />
          <Tooltip
            cursor={{ stroke: 'var(--baseline)', strokeWidth: 1 }}
            content={({ active, payload, label }) =>
              active && payload?.length ? (
                <TooltipBox
                  title={label}
                  rows={[
                    { label: 'Negative', value: payload.find((p) => p.dataKey === 'negative')?.value ?? 0, color: NEGATIVE },
                    { label: 'Neutral', value: payload.find((p) => p.dataKey === 'neutral')?.value ?? 0, color: NEUTRAL },
                    { label: 'Positive', value: payload.find((p) => p.dataKey === 'positive')?.value ?? 0, color: POSITIVE },
                  ]}
                />
              ) : null
            }
          />
          <Area type="linear" dataKey="negative" stackId="1" stroke={NEGATIVE}
                fill={NEGATIVE} fillOpacity={0.85} strokeWidth={2} />
          <Area type="linear" dataKey="neutral" stackId="1" stroke={NEUTRAL}
                fill={NEUTRAL} fillOpacity={0.85} strokeWidth={2} />
          <Area type="linear" dataKey="positive" stackId="1" stroke={POSITIVE}
                fill={POSITIVE} fillOpacity={0.85} strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>

      <Legend
        items={[
          { label: 'Negative', color: NEGATIVE },
          { label: 'Neutral', color: NEUTRAL },
          { label: 'Positive', color: POSITIVE },
        ]}
      />
    </div>
  )
}

export function Legend({ items }) {
  return (
    <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5">
      {items.map((item) => (
        <li key={item.label} className="flex items-center gap-1.5 text-xs"
            style={{ color: 'var(--text-secondary)' }}>
          <span className="inline-block h-2 w-2 rounded-full"
                style={{ background: item.color }} aria-hidden="true" />
          {item.label}
        </li>
      ))}
    </ul>
  )
}

/**
 * Which aspects draw complaints. Sorted by negative count.
 *
 * One hue, because this is magnitude within a single measure - giving each bar
 * its own colour would imply the categories differ in kind, which they do not.
 * Bars carry their own value labels so the axis is only a sanity check.
 */
export function AspectChart({ data }) {
  const rows = (data || [])
    .filter((row) => row.negative > 0)
    .sort((a, b) => b.negative - a.negative)
    .slice(0, 8)
    .map((row) => ({ ...row, name: prettyAspect(row.aspect) }))

  if (!rows.length) return <EmptyNote>No negative aspects detected yet.</EmptyNote>

  return (
    <ResponsiveContainer width="100%" height={Math.max(180, rows.length * 38)}>
      <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 40, left: 8, bottom: 4 }}>
        <CartesianGrid stroke="#d9e3d6" horizontal={false} />
        <XAxis type="number" {...axisProps} allowDecimals={false} />
        <YAxis type="category" dataKey="name" {...axisProps} width={110} axisLine={false} />
        <Tooltip
          cursor={{ fill: 'rgba(21,36,27,0.04)' }}
          content={({ active, payload }) =>
            active && payload?.length ? (
              <TooltipBox
                title={payload[0].payload.name}
                rows={[
                  { label: 'Negative mentions', value: payload[0].payload.negative, color: NEGATIVE },
                  { label: 'Total mentions', value: payload[0].payload.total, color: NEUTRAL },
                  {
                    label: 'Negative share',
                    value: `${Math.round(payload[0].payload.negative_share * 100)}%`,
                    color: NEUTRAL,
                  },
                ]}
              />
            ) : null
          }
        />
        <Bar dataKey="negative" radius={[0, 4, 4, 0]} barSize={18}
             label={{ position: 'right', fill: '#405346', fontSize: 11 }}>
          {rows.map((row) => (
            <Cell key={row.aspect} fill={NEGATIVE} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

/** Branch comparison - share of reviews that are negative. */
export function BranchChart({ data }) {
  const rows = (data || [])
    .filter((row) => row.total > 0)
    .sort((a, b) => b.negative_share - a.negative_share)
    .map((row) => ({
      ...row,
      name: row.branch_name,
      pct: Math.round(row.negative_share * 100),
    }))

  if (!rows.length) return <EmptyNote>No branch data yet.</EmptyNote>

  return (
    <ResponsiveContainer width="100%" height={Math.max(160, rows.length * 44)}>
      <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 48, left: 8, bottom: 4 }}>
        <CartesianGrid stroke="#d9e3d6" horizontal={false} />
        <XAxis type="number" {...axisProps} domain={[0, 100]} unit="%" />
        <YAxis type="category" dataKey="name" {...axisProps} width={100} axisLine={false} />
        <Tooltip
          cursor={{ fill: 'rgba(21,36,27,0.04)' }}
          content={({ active, payload }) =>
            active && payload?.length ? (
              <TooltipBox
                title={payload[0].payload.name}
                rows={[
                  { label: 'Negative', value: payload[0].payload.negative, color: NEGATIVE },
                  { label: 'Total reviews', value: payload[0].payload.total, color: NEUTRAL },
                ]}
              />
            ) : null
          }
        />
        <Bar dataKey="pct" radius={[0, 4, 4, 0]} barSize={18} fill={NEGATIVE}
             label={{ position: 'right', formatter: (v) => `${v}%`, fill: '#405346', fontSize: 11 }} />
      </BarChart>
    </ResponsiveContainer>
  )
}
