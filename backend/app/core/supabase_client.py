from functools import lru_cache

from loguru import logger
from supabase import Client, create_client

from app.config import settings


@lru_cache
def get_supabase_client() -> Client:
    """Supabaseクライアントのシングルトンインスタンスを返す"""
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        raise ValueError("SUPABASE_URL と SUPABASE_ANON_KEY を .env に設定してください")

    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    logger.info("Supabaseクライアントを初期化しました")
    return client


@lru_cache
def get_supabase_admin_client() -> Client:
    """管理者権限（service_role）のSupabaseクライアントを返す"""
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise ValueError(
            "SUPABASE_URL と SUPABASE_SERVICE_ROLE_KEY を .env に設定してください"
        )

    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    return client


def check_supabase_connection() -> bool:
    """Supabase接続の死活確認"""
    try:
        client = get_supabase_client()
        # usersテーブルに対してダミークエリを実行して接続確認
        client.table("users").select("id").limit(1).execute()
        return True
    except Exception as error:
        logger.error("Supabase接続エラー", error=str(error))
        return False
