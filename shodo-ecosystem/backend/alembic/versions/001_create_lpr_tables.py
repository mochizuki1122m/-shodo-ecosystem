"""Create LPR tables

Revision ID: 001_lpr_tables
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = '001_lpr_tables'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """LPRシステムのテーブルを作成"""
    
    # ユーザーテーブル（既存の場合はスキップ、新規の場合は作成）
    op.create_table('users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('username', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('lpr_enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('max_lpr_tokens', sa.Integer(), nullable=False, default=10),
        sa.Column('lpr_default_ttl', sa.Integer(), nullable=False, default=3600),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
        sa.UniqueConstraint('email')
    )
    
    # LPRトークンテーブル
    op.create_table('lpr_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('jti', sa.String(255), nullable=False),
        sa.Column('version', sa.String(10), nullable=False, default='1.0.0'),
        sa.Column('subject_pseudonym', sa.String(64), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('issued_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('device_fingerprint_hash', sa.String(64), nullable=False),
        sa.Column('device_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('origin_allowlist', postgresql.ARRAY(sa.String), nullable=False),
        sa.Column('scope_allowlist', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('policy', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('correlation_id', sa.String(64), nullable=False),
        sa.Column('parent_session_id', sa.String(255), nullable=True),
        sa.Column('revoked', sa.Boolean(), nullable=False, default=False),
        sa.Column('revocation_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revocation_reason', sa.Text(), nullable=True),
        sa.Column('revoked_by', sa.String(255), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=False, default=0),
        sa.Column('last_request_url', sa.Text(), nullable=True),
        sa.Column('last_request_method', sa.String(10), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('jti'),
        sa.CheckConstraint('expires_at > issued_at', name='check_expiry_after_issue')
    )
    
    # LPRトークンのインデックス
    op.create_index('idx_lpr_jti', 'lpr_tokens', ['jti'])
    op.create_index('idx_lpr_subject', 'lpr_tokens', ['subject_pseudonym'])
    op.create_index('idx_lpr_expires', 'lpr_tokens', ['expires_at'])
    op.create_index('idx_lpr_revoked', 'lpr_tokens', ['revoked'])
    op.create_index('idx_lpr_active', 'lpr_tokens', ['subject_pseudonym', 'expires_at', 'revoked'])
    op.create_index('idx_lpr_correlation', 'lpr_tokens', ['correlation_id'])
    op.create_index('idx_lpr_device', 'lpr_tokens', ['device_fingerprint_hash'])
    
    # 監査ログテーブル
    op.create_table('audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('sequence_number', sa.Integer(), nullable=False),
        sa.Column('who', sa.String(255), nullable=False),
        sa.Column('when', sa.DateTime(timezone=True), nullable=False),
        sa.Column('what', sa.Text(), nullable=False),
        sa.Column('where', sa.String(255), nullable=False),
        sa.Column('why', sa.Text(), nullable=False),
        sa.Column('how', sa.String(255), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('result', sa.String(20), nullable=False),
        sa.Column('correlation_id', sa.String(64), nullable=False),
        sa.Column('session_id', sa.String(255), nullable=True),
        sa.Column('request_id', sa.String(64), nullable=True),
        sa.Column('lpr_token_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('client_ip', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('previous_hash', sa.String(64), nullable=False),
        sa.Column('entry_hash', sa.String(64), nullable=False),
        sa.Column('signature', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['lpr_token_id'], ['lpr_tokens.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sequence_number'),
        sa.UniqueConstraint('entry_hash')
    )
    
    # 監査ログのインデックス
    op.create_index('idx_audit_sequence', 'audit_logs', ['sequence_number'])
    op.create_index('idx_audit_who', 'audit_logs', ['who'])
    op.create_index('idx_audit_when', 'audit_logs', ['when'])
    op.create_index('idx_audit_event_type', 'audit_logs', ['event_type'])
    op.create_index('idx_audit_severity', 'audit_logs', ['severity'])
    op.create_index('idx_audit_correlation', 'audit_logs', ['correlation_id'])
    op.create_index('idx_audit_event', 'audit_logs', ['event_type', 'when'])
    op.create_index('idx_audit_who_when', 'audit_logs', ['who', 'when'])
    op.create_index('idx_audit_severity_when', 'audit_logs', ['severity', 'when'])
    
    # デバイス指紋テーブル
    op.create_table('device_fingerprints',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('fingerprint_hash', sa.String(64), nullable=False),
        sa.Column('user_agent', sa.Text(), nullable=False),
        sa.Column('accept_language', sa.String(255), nullable=False),
        sa.Column('screen_resolution', sa.String(20), nullable=True),
        sa.Column('timezone', sa.String(50), nullable=True),
        sa.Column('platform', sa.String(50), nullable=True),
        sa.Column('hardware_concurrency', sa.Integer(), nullable=True),
        sa.Column('device_memory', sa.Integer(), nullable=True),
        sa.Column('canvas_fingerprint', sa.Text(), nullable=True),
        sa.Column('webgl_fingerprint', sa.Text(), nullable=True),
        sa.Column('audio_fingerprint', sa.Text(), nullable=True),
        sa.Column('trust_score', sa.Float(), nullable=False, default=0.5),
        sa.Column('first_seen', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=False),
        sa.Column('usage_count', sa.Integer(), nullable=False, default=1),
        sa.Column('user_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('fingerprint_hash')
    )
    
    # デバイス指紋のインデックス
    op.create_index('idx_device_hash', 'device_fingerprints', ['fingerprint_hash'])
    op.create_index('idx_device_trust', 'device_fingerprints', ['trust_score', 'last_seen'])
    op.create_index('idx_device_usage', 'device_fingerprints', ['usage_count', 'last_seen'])
    
    # レート制限バケットテーブル
    op.create_table('rate_limit_buckets',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('bucket_key', sa.String(255), nullable=False),
        sa.Column('bucket_type', sa.String(50), nullable=False),
        sa.Column('tokens', sa.Float(), nullable=False, default=0.0),
        sa.Column('max_tokens', sa.Float(), nullable=False),
        sa.Column('refill_rate', sa.Float(), nullable=False),
        sa.Column('last_refill', sa.DateTime(timezone=True), nullable=False),
        sa.Column('total_requests', sa.Integer(), nullable=False, default=0),
        sa.Column('rejected_requests', sa.Integer(), nullable=False, default=0),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('bucket_key')
    )
    
    # レート制限のインデックス
    op.create_index('idx_ratelimit_key', 'rate_limit_buckets', ['bucket_key', 'bucket_type'])
    op.create_index('idx_ratelimit_refill', 'rate_limit_buckets', ['last_refill'])
    
    # LPR使用ログテーブル
    op.create_table('lpr_usage_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('lpr_token_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('jti', sa.String(255), nullable=False),
        sa.Column('request_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('request_method', sa.String(10), nullable=False),
        sa.Column('request_url', sa.Text(), nullable=False),
        sa.Column('request_origin', sa.String(255), nullable=True),
        sa.Column('request_size', sa.Integer(), nullable=True),
        sa.Column('response_status', sa.Integer(), nullable=True),
        sa.Column('response_size', sa.Integer(), nullable=True),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column('validation_result', sa.String(20), nullable=False),
        sa.Column('validation_error', sa.Text(), nullable=True),
        sa.Column('device_fingerprint_match', sa.Boolean(), nullable=True),
        sa.Column('client_ip', sa.String(45), nullable=True),
        sa.Column('correlation_id', sa.String(64), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['lpr_token_id'], ['lpr_tokens.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 使用ログのインデックス
    op.create_index('idx_usage_jti', 'lpr_usage_logs', ['jti'])
    op.create_index('idx_usage_time', 'lpr_usage_logs', ['request_time'])
    op.create_index('idx_usage_token_time', 'lpr_usage_logs', ['lpr_token_id', 'request_time'])
    op.create_index('idx_usage_correlation', 'lpr_usage_logs', ['correlation_id'])
    op.create_index('idx_usage_result', 'lpr_usage_logs', ['validation_result', 'request_time'])
    
    # LPR失効リストテーブル
    op.create_table('lpr_revocation_list',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('jti', sa.String(255), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('revoked_by', sa.String(255), nullable=False),
        sa.Column('original_expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('subject_pseudonym', sa.String(64), nullable=False),
        sa.Column('notification_sent', sa.Boolean(), nullable=False, default=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('jti')
    )
    
    # 失効リストのインデックス
    op.create_index('idx_revocation_jti', 'lpr_revocation_list', ['jti'])
    op.create_index('idx_revocation_time', 'lpr_revocation_list', ['revoked_at'])
    op.create_index('idx_revocation_expires', 'lpr_revocation_list', ['original_expires_at'])


def downgrade() -> None:
    """テーブルを削除"""
    
    # インデックスとテーブルを逆順で削除
    op.drop_table('lpr_revocation_list')
    op.drop_table('lpr_usage_logs')
    op.drop_table('rate_limit_buckets')
    op.drop_table('device_fingerprints')
    op.drop_table('audit_logs')
    op.drop_table('lpr_tokens')
    op.drop_table('users')