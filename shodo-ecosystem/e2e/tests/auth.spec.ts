import { test, expect } from '@playwright/test';

test.describe('認証フロー', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('ログインページが表示される', async ({ page }) => {
    await page.click('text=ログイン');
    await expect(page).toHaveURL('/login');
    await expect(page.locator('h1')).toContainText('ログイン');
  });

  test('正常なログインフロー', async ({ page }) => {
    // ログインページへ移動
    await page.goto('/login');
    
    // フォームに入力
    await page.fill('input[name="email"]', 'test@example.com');
    await page.fill('input[name="password"]', 'TestPassword123!');
    
    // ログインボタンをクリック
    await page.click('button[type="submit"]');
    
    // ダッシュボードにリダイレクトされることを確認
    await expect(page).toHaveURL('/dashboard');
    
    // ユーザー名が表示されることを確認
    await expect(page.locator('[data-testid="user-name"]')).toContainText('testuser');
  });

  test('無効な認証情報でのログイン', async ({ page }) => {
    await page.goto('/login');
    
    await page.fill('input[name="email"]', 'wrong@example.com');
    await page.fill('input[name="password"]', 'WrongPassword');
    
    await page.click('button[type="submit"]');
    
    // エラーメッセージが表示されることを確認
    await expect(page.locator('.error-message')).toContainText('メールアドレスまたはパスワードが正しくありません');
    
    // URLが変わらないことを確認
    await expect(page).toHaveURL('/login');
  });

  test('ユーザー登録フロー', async ({ page }) => {
    await page.goto('/register');
    
    // フォームに入力
    await page.fill('input[name="email"]', 'newuser@example.com');
    await page.fill('input[name="username"]', 'newuser');
    await page.fill('input[name="password"]', 'SecurePassword123!');
    await page.fill('input[name="confirmPassword"]', 'SecurePassword123!');
    
    // 利用規約に同意
    await page.check('input[name="agreeToTerms"]');
    
    // 登録ボタンをクリック
    await page.click('button[type="submit"]');
    
    // 成功メッセージが表示されることを確認
    await expect(page.locator('.success-message')).toContainText('登録が完了しました');
    
    // ログインページにリダイレクトされることを確認
    await expect(page).toHaveURL('/login');
  });

  test('パスワードリセットフロー', async ({ page }) => {
    await page.goto('/login');
    
    // パスワードを忘れた場合のリンクをクリック
    await page.click('text=パスワードを忘れた場合');
    
    await expect(page).toHaveURL('/password-reset');
    
    // メールアドレスを入力
    await page.fill('input[name="email"]', 'test@example.com');
    
    // リセットリンク送信ボタンをクリック
    await page.click('button[type="submit"]');
    
    // 成功メッセージが表示されることを確認
    await expect(page.locator('.success-message')).toContainText('パスワードリセットのリンクをメールで送信しました');
  });

  test('ログアウトフロー', async ({ page }) => {
    // まずログイン
    await page.goto('/login');
    await page.fill('input[name="email"]', 'test@example.com');
    await page.fill('input[name="password"]', 'TestPassword123!');
    await page.click('button[type="submit"]');
    
    await expect(page).toHaveURL('/dashboard');
    
    // ユーザーメニューを開く
    await page.click('[data-testid="user-avatar"]');
    
    // ログアウトをクリック
    await page.click('text=ログアウト');
    
    // ホームページにリダイレクトされることを確認
    await expect(page).toHaveURL('/');
    
    // ログインボタンが表示されることを確認
    await expect(page.locator('text=ログイン')).toBeVisible();
  });

  test('認証が必要なページへのアクセス', async ({ page }) => {
    // 未認証状態でダッシュボードにアクセス
    await page.goto('/dashboard');
    
    // ログインページにリダイレクトされることを確認
    await expect(page).toHaveURL('/login');
    
    // リダイレクトメッセージが表示されることを確認
    await expect(page.locator('.info-message')).toContainText('このページにアクセスするにはログインが必要です');
  });

  test('セッションタイムアウト', async ({ page, context }) => {
    // ログイン
    await page.goto('/login');
    await page.fill('input[name="email"]', 'test@example.com');
    await page.fill('input[name="password"]', 'TestPassword123!');
    await page.click('button[type="submit"]');
    
    // セッションクッキーを削除（タイムアウトをシミュレート）
    await context.clearCookies();
    
    // ページをリロード
    await page.reload();
    
    // ログインページにリダイレクトされることを確認
    await expect(page).toHaveURL('/login');
    await expect(page.locator('.warning-message')).toContainText('セッションがタイムアウトしました');
  });
});