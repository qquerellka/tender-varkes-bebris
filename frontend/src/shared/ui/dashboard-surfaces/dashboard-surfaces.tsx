import { Button } from 'antd'
import styled, { css } from 'styled-components'

export type SurfaceTone = 'cool' | 'warm'
export type PillTone =
  | 'neutral'
  | 'accent'
  | 'success'
  | 'warning'
  | 'danger'
  | 'supplier'
  | 'info'
  | 'purple'
export type ButtonTone = 'neutral' | 'accent' | 'success' | 'danger'
export type ButtonEmphasis = 'outline' | 'soft' | 'solid'

const surfaceToneStyles = {
  cool: css`
    --snapshot-border: #dde6ef;
    --snapshot-background: linear-gradient(180deg, rgba(248, 251, 254, 1) 0%, rgba(255, 255, 255, 1) 100%);
    --snapshot-label: #7b8797;
    --snapshot-value: #2c4262;
    --snapshot-hint: #62748a;
  `,
  warm: css`
    --snapshot-border: #e2ddd5;
    --snapshot-background: linear-gradient(180deg, rgba(252, 248, 243, 1) 0%, rgba(255, 255, 255, 1) 100%);
    --snapshot-label: #8b7967;
    --snapshot-value: #5a3f22;
    --snapshot-hint: #6f7d8e;
  `,
}

export const SnapshotGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;

  @media (max-width: 620px) {
    grid-template-columns: 1fr;
  }
`

export const SnapshotCard = styled.div<{ $tone?: SurfaceTone }>`
  ${({ $tone = 'cool' }) => surfaceToneStyles[$tone]}

  display: grid;
  gap: 4px;
  padding: 14px 16px;
  border: 1px solid var(--snapshot-border);
  background: var(--snapshot-background);
`

export const SnapshotLabel = styled.span`
  color: var(--snapshot-label);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
`

export const SnapshotValue = styled.span`
  color: var(--snapshot-value);
  font-size: 16px;
  font-weight: 800;
  line-height: 1.35;
`

export const SnapshotHint = styled.span`
  color: var(--snapshot-hint);
  font-size: 12px;
  line-height: 1.45;
`

export const EmptyStateBlock = styled.div<{ $gap?: number; $padding?: 'none' | 'compact' }>`
  display: grid;
  gap: ${({ $gap = 12 }) => `${$gap}px`};
  justify-items: start;
  padding: ${({ $padding = 'none' }) => ($padding === 'compact' ? '8px 0 2px' : '0')};
`

export const EmptyStateText = styled.span<{ $size?: 'sm' | 'md' }>`
  color: #67768a;
  font-size: ${({ $size = 'sm' }) => ($size === 'md' ? '14px' : '13px')};
  line-height: 1.5;
`

export const ActivityTimeline = styled.div`
  display: grid;
  gap: 12px;
`

export const ActivityCard = styled.div`
  display: grid;
  gap: 8px;
  padding: 14px 16px;
  border: 1px solid #dde6ef;
  background: #fbfcfe;
`

export const ActivityTop = styled.div`
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
`

export const ActivityMeta = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
`

export const ActivityTitle = styled.span`
  color: #2b3f5d;
  font-size: 14px;
  font-weight: 700;
`

export const ActivityText = styled.span`
  color: #64748a;
  font-size: 13px;
  line-height: 1.5;
`

export const InlineActionRow = styled.div<{ $gap?: number }>`
  display: flex;
  flex-wrap: wrap;
  gap: ${({ $gap = 8 }) => `${$gap}px`};
`

export const HeroIntroBlock = styled.div`
  display: grid;
  gap: 10px;
  align-content: start;
`

export const HeroEyebrow = styled.span`
  color: #c26d2d;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
`

export const HeroTitle = styled.span`
  color: #24364f;
  font-size: 28px;
  font-weight: 800;
  line-height: 1.05;
`

export const HeroText = styled.span`
  color: #5d6f84;
  font-size: 15px;
  line-height: 1.55;
  max-width: 64ch;
`

export const HeroActionRow = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
`

const onboardingToneStyles = {
  cool: css`
    --onboarding-background: linear-gradient(135deg, rgba(255, 255, 255, 0.98) 0%, rgba(244, 248, 253, 0.98) 100%);
    --onboarding-card-border: #dbe4ed;
    --onboarding-card-hover: #f7fbff;
    --onboarding-card-hover-border: #2f4f84;
    --onboarding-card-title: #2b4365;
    --onboarding-card-action: #2f4f84;
    --onboarding-text: #5f7085;
  `,
  warm: css`
    --onboarding-background: linear-gradient(135deg, rgba(255, 255, 255, 0.98) 0%, rgba(249, 243, 236, 0.98) 100%);
    --onboarding-card-border: #e5ddd4;
    --onboarding-card-hover: #fffaf4;
    --onboarding-card-hover-border: #c26d2d;
    --onboarding-card-title: #7c4a1a;
    --onboarding-card-action: #c26d2d;
    --onboarding-text: #607085;
  `,
}

export const OnboardingSurface = styled.section<{ $tone?: SurfaceTone; $padding?: 'md' | 'lg' }>`
  ${({ $tone = 'cool' }) => onboardingToneStyles[$tone]}

  display: grid;
  gap: 16px;
  margin-top: 18px;
  padding: ${({ $padding = 'md' }) => ($padding === 'lg' ? '20px' : '18px 20px')};
  border: 1px solid #d9e0e8;
  background: var(--onboarding-background);
  box-shadow: 0 10px 24px rgba(74, 92, 117, 0.05);
`

export const OnboardingHeader = styled.div`
  display: grid;
  gap: 6px;
`

export const OnboardingTitle = styled.span`
  color: #2a3c56;
  font-size: 20px;
  font-weight: 800;
`

export const OnboardingText = styled.span`
  color: var(--onboarding-text);
  font-size: 14px;
  line-height: 1.5;
`

export const OnboardingGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;

  @media (max-width: 1100px) {
    grid-template-columns: 1fr;
  }
`

export const OnboardingCard = styled.button<{ $tone?: SurfaceTone }>`
  ${({ $tone = 'cool' }) => onboardingToneStyles[$tone]}

  display: grid;
  gap: 8px;
  padding: 16px;
  border: 1px solid var(--onboarding-card-border);
  color: #273a53;
  font: inherit;
  text-align: left;
  background: #fff;
  cursor: pointer;

  &:hover {
    border-color: var(--onboarding-card-hover-border);
    background: var(--onboarding-card-hover);
  }
`

export const OnboardingCardTitle = styled.span<{ $tone?: SurfaceTone }>`
  ${({ $tone = 'cool' }) => onboardingToneStyles[$tone]}

  color: var(--onboarding-card-title);
  font-size: 15px;
  font-weight: 800;
`

export const OnboardingCardText = styled.span`
  color: #66778c;
  font-size: 13px;
  line-height: 1.45;
`

export const OnboardingCardAction = styled.span<{ $tone?: SurfaceTone }>`
  ${({ $tone = 'cool' }) => onboardingToneStyles[$tone]}

  color: var(--onboarding-card-action);
  font-size: 13px;
  font-weight: 800;
  text-transform: uppercase;
`

export const SectionSurface = styled.section<{ $padding?: 'none' | 'md'; $gap?: number }>`
  display: grid;
  gap: ${({ $gap = 14 }) => `${$gap}px`};
  padding: ${({ $padding = 'none' }) => ($padding === 'md' ? '18px' : '0')};
  border: 1px solid #d9e0e8;
  background: #fff;
  box-shadow: 0 10px 24px rgba(74, 92, 117, 0.05);
`

export const SectionHeaderBar = styled.div<{ $padding?: 'none' | 'content'; $bordered?: boolean }>`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: ${({ $padding = 'none' }) => ($padding === 'content' ? '18px 20px' : '0')};
  border-bottom: ${({ $bordered = false }) => ($bordered ? '1px solid #e1e7ee' : '0')};
`

export const SectionHeadingStack = styled.div`
  display: grid;
  gap: 4px;
`

export const SectionHeading = styled.span`
  color: #314158;
  font-size: 18px;
  font-weight: 700;
  line-height: 1.35;
`

export const SectionHeadingHint = styled.span`
  color: #6a798c;
  font-size: 13px;
  line-height: 1.45;
`

export const MetricGrid = styled.div<{ $columns?: 2 | 4 }>`
  display: grid;
  grid-template-columns: repeat(${({ $columns = 2 }) => $columns}, minmax(0, 1fr));
  gap: 10px;

  @media (max-width: 980px) {
    grid-template-columns: repeat(${({ $columns = 2 }) => ($columns === 4 ? 2 : 1)}, minmax(0, 1fr));
  }

  @media (max-width: 620px) {
    grid-template-columns: 1fr;
  }
`

export const MetricCard = styled.div`
  display: grid;
  gap: 4px;
  padding: 12px 14px;
  border: 1px solid #e1e8f0;
  background: #fbfcfe;
`

export const MetricValue = styled.span<{ $size?: 'md' | 'lg' }>`
  color: #2a3f5e;
  font-size: ${({ $size = 'md' }) => ($size === 'lg' ? '22px' : '20px')};
  font-weight: 800;
`

export const MetricLabel = styled.span`
  color: #7a889b;
  font-size: 12px;
  line-height: 1.4;
`

export const HintSurface = styled.div`
  display: grid;
  gap: 12px;
  padding: 16px;
  border: 1px solid #dde6ef;
  background: #fbfcfe;
`

export const HintText = styled.span`
  color: #64748a;
  font-size: 14px;
  line-height: 1.5;
`

export const DetailList = styled.div`
  display: grid;
  gap: 10px;
`

export const DetailCard = styled.div`
  display: grid;
  gap: 5px;
  padding: 14px;
  border: 1px solid #e1e8f0;
  background: #fbfcfe;
`

export const DetailTitle = styled.span`
  color: #273a53;
  font-size: 14px;
  font-weight: 700;
`

export const DetailMeta = styled.span`
  color: #6f7d8e;
  font-size: 12px;
  line-height: 1.45;
`

const pillToneStyles = {
  neutral: css`
    --pill-border: #dde5ee;
    --pill-color: #5e6f84;
    --pill-bg: #f8fbfe;
  `,
  accent: css`
    --pill-border: #cfdcf0;
    --pill-color: #2f4f84;
    --pill-bg: #f3f7fd;
  `,
  success: css`
    --pill-border: #cfe6da;
    --pill-color: #226246;
    --pill-bg: #eef8f2;
  `,
  warning: css`
    --pill-border: #eadac0;
    --pill-color: #7a5a1d;
    --pill-bg: #fff8ea;
  `,
  danger: css`
    --pill-border: #efc9c5;
    --pill-color: #9e3a32;
    --pill-bg: #fff2f1;
  `,
  supplier: css`
    --pill-border: #ecd7c6;
    --pill-color: #8a4a14;
    --pill-bg: #fff1e4;
  `,
  info: css`
    --pill-border: #d5dff1;
    --pill-color: #3b5f95;
    --pill-bg: #eef4ff;
  `,
  purple: css`
    --pill-border: #ddd4ef;
    --pill-color: #69479a;
    --pill-bg: #f5f0ff;
  `,
}

export const StatusPill = styled.span<{ $tone?: PillTone }>`
  ${({ $tone = 'neutral' }) => pillToneStyles[$tone]}

  display: inline-flex;
  align-items: center;
  width: fit-content;
  padding: 5px 10px;
  border: 1px solid var(--pill-border);
  color: var(--pill-color);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  background: var(--pill-bg);
`

const buttonToneStyles = {
  neutral: {
    outline: css`
      --button-border: #d7dfe8;
      --button-color: #4f6788;
      --button-bg: #fff;
      --button-hover-border: #bfd0e2;
      --button-hover-bg: #f7fbff;
      --button-hover-color: #30517f;
    `,
    soft: css`
      --button-border: #d7e1ec;
      --button-color: #4f6788;
      --button-bg: #f8fbfe;
      --button-hover-border: #bfd0e2;
      --button-hover-bg: #eef5fc;
      --button-hover-color: #30517f;
    `,
    solid: css`
      --button-border: #2f4f84;
      --button-color: #fff;
      --button-bg: #2f4f84;
      --button-hover-border: #27456f;
      --button-hover-bg: #27456f;
      --button-hover-color: #fff;
    `,
  },
  accent: {
    outline: css`
      --button-border: #cfdcf0;
      --button-color: #2f4f84;
      --button-bg: #fff;
      --button-hover-border: #b5cae8;
      --button-hover-bg: #f4f8fd;
      --button-hover-color: #27456f;
    `,
    soft: css`
      --button-border: #d6e1f1;
      --button-color: #2f4f84;
      --button-bg: #f3f7fd;
      --button-hover-border: #b5cae8;
      --button-hover-bg: #eaf1fb;
      --button-hover-color: #27456f;
    `,
    solid: css`
      --button-border: #2f4f84;
      --button-color: #fff;
      --button-bg: #2f4f84;
      --button-hover-border: #27456f;
      --button-hover-bg: #27456f;
      --button-hover-color: #fff;
    `,
  },
  success: {
    outline: css`
      --button-border: #cfe6da;
      --button-color: #226246;
      --button-bg: #fff;
      --button-hover-border: #b7d8c6;
      --button-hover-bg: #eef8f2;
      --button-hover-color: #1b543b;
    `,
    soft: css`
      --button-border: #cfe6da;
      --button-color: #226246;
      --button-bg: #eef8f2;
      --button-hover-border: #b7d8c6;
      --button-hover-bg: #e3f3ea;
      --button-hover-color: #1b543b;
    `,
    solid: css`
      --button-border: #226246;
      --button-color: #fff;
      --button-bg: #226246;
      --button-hover-border: #1b543b;
      --button-hover-bg: #1b543b;
      --button-hover-color: #fff;
    `,
  },
  danger: {
    outline: css`
      --button-border: #efc9c5;
      --button-color: #9e3a32;
      --button-bg: #fff;
      --button-hover-border: #e7b4ae;
      --button-hover-bg: #fff4f3;
      --button-hover-color: #8a3029;
    `,
    soft: css`
      --button-border: #efc9c5;
      --button-color: #9e3a32;
      --button-bg: #fff2f1;
      --button-hover-border: #e7b4ae;
      --button-hover-bg: #fee8e6;
      --button-hover-color: #8a3029;
    `,
    solid: css`
      --button-border: #b33c33;
      --button-color: #fff;
      --button-bg: #b33c33;
      --button-hover-border: #982e26;
      --button-hover-bg: #982e26;
      --button-hover-color: #fff;
    `,
  },
} as const

export const SurfaceButton = styled(Button)<{
  $tone?: ButtonTone
  $emphasis?: ButtonEmphasis
}>`
  ${({ $tone = 'neutral', $emphasis = 'outline' }) => buttonToneStyles[$tone][$emphasis]}

  &.ant-btn {
    border-color: var(--button-border);
    color: var(--button-color);
    background: var(--button-bg);
    box-shadow: none;
    font-weight: 700;
  }

  &.ant-btn:not(:disabled):hover,
  &.ant-btn:not(:disabled):focus {
    border-color: var(--button-hover-border);
    color: var(--button-hover-color);
    background: var(--button-hover-bg);
  }
`
