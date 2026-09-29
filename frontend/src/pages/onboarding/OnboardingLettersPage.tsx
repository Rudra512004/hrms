/**
 * Candidate onboarding — issued letters (Offer + Appointment).
 */
import React, { useState, useEffect } from 'react';
import { FileText, ChevronDown, ChevronUp, Loader2 } from 'lucide-react';
import { candidatePortalService, type IssuedLetter } from '../../services/candidates';

function LetterCard({ letter }: { letter: IssuedLetter }) {
  const [open, setOpen] = useState(true);
  return (
    <div style={{
      border: '1px solid var(--color-border)', borderRadius: '12px',
      overflow: 'hidden', marginBottom: '16px',
    }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '14px 18px', border: 'none', background: 'var(--color-bg-card)',
          cursor: 'pointer', color: 'var(--color-text-main)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <FileText size={18} style={{ color: 'var(--color-primary)' }} />
          <div style={{ textAlign: 'left' }}>
            <div style={{ fontWeight: 700, fontSize: '0.95rem' }}>{letter.letter_type_display}</div>
            <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', marginTop: '2px' }}>
              Issued on {new Date(letter.issued_at).toLocaleDateString()}
            </div>
          </div>
        </div>
        {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>
      {open && (
        <div style={{
          padding: '20px 24px', borderTop: '1px solid var(--color-border)',
          background: 'var(--color-bg-body)',
        }}>
          <div style={{ fontWeight: 700, fontSize: '1rem', marginBottom: '16px', color: 'var(--color-text-main)' }}>
            {letter.subject_snapshot}
          </div>
          <div style={{
            whiteSpace: 'pre-wrap', fontSize: '0.9rem', lineHeight: 1.7,
            color: 'var(--color-text-main)', fontFamily: 'Georgia, serif',
          }}>
            {letter.body_snapshot}
          </div>
        </div>
      )}
    </div>
  );
}

export const OnboardingLettersPage: React.FC = () => {
  const [letters, setLetters] = useState<IssuedLetter[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    candidatePortalService.getLetters()
      .then(setLetters)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div style={{ maxWidth: '800px' }}>
      <h1 style={{ margin: '0 0 4px', fontSize: '1.4rem', fontWeight: 700, color: 'var(--color-text-main)' }}>
        My Letters
      </h1>
      <p style={{ margin: '0 0 24px', color: 'var(--color-text-muted)' }}>
        Letters issued to you by HR — snapshots preserved at issue time.
      </p>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px', color: 'var(--color-text-muted)' }}>
          <Loader2 size={24} style={{ animation: 'spin 1s linear infinite', marginBottom: '8px' }} />
        </div>
      ) : error ? (
        <div style={{ color: '#ef4444' }}>{error}</div>
      ) : letters.length === 0 ? (
        <div style={{
          textAlign: 'center', padding: '60px',
          border: '2px dashed var(--color-border)', borderRadius: '12px',
          color: 'var(--color-text-muted)',
        }}>
          <FileText size={36} style={{ opacity: 0.3, marginBottom: '12px' }} />
          <p style={{ margin: 0 }}>No letters have been issued to you yet.</p>
        </div>
      ) : (
        letters.map(l => <LetterCard key={l.id} letter={l} />)
      )}
    </div>
  );
};
