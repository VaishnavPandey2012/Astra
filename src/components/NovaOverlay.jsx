import React, { useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { NOVA_STATES } from '../hooks/useNovaState'

// ── Animation variants ────────────────────────────────────────────────────────

/** Framer Motion variants for the four glow strips */
const stripVariants = {
  hidden: {
    opacity: 0,
    filter:  'blur(4px)',
  },
  listening: {
    opacity: [0.55, 0.9, 0.55],
    filter:  'blur(10px)',
    transition: {
      opacity:  { duration: 2.5, repeat: Infinity, ease: 'easeInOut' },
      filter:   { duration: 0.4 },
    },
  },
  processing: {
    opacity: 1,
    filter:  'blur(8px)',
    transition: { duration: 0.3 },
  },
  speaking: {
    opacity: 1,
    filter:  'blur(8px)',
    transition: { duration: 0.2 },
  },
}

/** Transcript / response text fade variants */
const textVariants = {
  hidden:  { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.35, ease: 'easeOut' } },
  exit:    { opacity: 0, y: -8, transition: { duration: 0.25 } },
}

/** Status badge fade variants */
const badgeVariants = {
  hidden:  { opacity: 0, scale: 0.9 },
  visible: { opacity: 0.85, scale: 1, transition: { duration: 0.3 } },
  exit:    { opacity: 0, scale: 0.9, transition: { duration: 0.2 } },
}

// ── Helper: map state → CSS class suffix ─────────────────────────────────────
const STATE_CLASS = {
  [NOVA_STATES.IDLE]:       '',
  [NOVA_STATES.LISTENING]:  'nova-listening',
  [NOVA_STATES.PROCESSING]: 'nova-processing',
  [NOVA_STATES.SPEAKING]:   'nova-speaking',
}

const STATUS_LABEL = {
  [NOVA_STATES.IDLE]:       '',
  [NOVA_STATES.LISTENING]:  'Listening…',
  [NOVA_STATES.PROCESSING]: 'Thinking…',
  [NOVA_STATES.SPEAKING]:   'Nova',
}

// ── GlowStrip sub-component ───────────────────────────────────────────────────
function GlowStrip ({ side, variant, amplitude }) {
  // When speaking, scale blur with audio amplitude for reactivity
  const extraBlur = variant === 'speaking' ? amplitude * 14 : 0
  const extraOpacity = variant === 'speaking' ? amplitude * 0.4 : 0

  return (
    <motion.div
      className={`glow-strip ${side}`}
      variants={stripVariants}
      initial="hidden"
      animate={variant === 'hidden' ? 'hidden' : variant}
      style={{
        ...(variant === 'speaking' && {
          filter:  `blur(${8 + extraBlur}px)`,
          opacity: Math.min(1, 0.75 + extraOpacity),
        }),
      }}
    />
  )
}

// ── Main overlay component ────────────────────────────────────────────────────
/**
 * NovaOverlay
 *
 * Props:
 *   state      {string}  – one of NOVA_STATES
 *   transcript {string}  – what the user said
 *   response   {string}  – Nova's reply text
 *   amplitude  {number}  – 0-1 audio amplitude for speaking reactivity
 */
export default function NovaOverlay ({ state, transcript, response, amplitude }) {
  const isActive = state !== NOVA_STATES.IDLE
  const glowVariant = isActive ? state : 'hidden'

  // Decide which text to show below the border
  const displayText = state === NOVA_STATES.SPEAKING
    ? response
    : state === NOVA_STATES.LISTENING
    ? transcript || ''
    : ''

  return (
    <div className={`nova-root ${STATE_CLASS[state] ?? ''}`}>

      {/* ── Four glow strips ─── */}
      {['top', 'bottom', 'left', 'right'].map((side) => (
        <GlowStrip
          key={side}
          side={side}
          variant={glowVariant}
          amplitude={amplitude}
        />
      ))}

      {/* ── Status badge ─── */}
      <AnimatePresence>
        {isActive && (
          <motion.div
            key="status"
            className="nova-status"
            variants={badgeVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
          >
            {STATUS_LABEL[state]}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Speaking waveform dots ─── */}
      <AnimatePresence>
        {state === NOVA_STATES.SPEAKING && (
          <motion.div
            key="waveform"
            className="nova-waveform"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            {[1, 2, 3, 4, 5].map((i) => (
              <span key={i} style={{ animationDelay: `${(i - 1) * 0.1}s` }} />
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Transcript / response text ─── */}
      <AnimatePresence mode="wait">
        {displayText && (
          <motion.p
            key={displayText}
            className="nova-transcript"
            variants={textVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
          >
            {displayText}
          </motion.p>
        )}
      </AnimatePresence>

    </div>
  )
}
