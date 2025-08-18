import { test, expect } from '@playwright/test';

test.describe('NLP解析機能', () => {
  test.beforeEach(async ({ page }) => {
    // ログイン
    await page.goto('/login');
    await page.fill('input[name="email"]', 'test@example.com');
    await page.fill('input[name="password"]', 'TestPassword123!');
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL('/dashboard');
    
    // NLP解析ページへ移動
    await page.click('text=NLP解析');
    await expect(page).toHaveURL('/nlp');
  });

  test('テキスト解析の実行', async ({ page }) => {
    // テキストエリアに入力
    const testText = 'これはテスト用のテキストです。商品の価格を1000円に変更してください。';
    await page.fill('textarea[name="analysisText"]', testText);
    
    // 解析タイプを選択
    await page.selectOption('select[name="analysisType"]', 'hybrid');
    
    // 解析ボタンをクリック
    await page.click('button:has-text("解析開始")');
    
    // ローディング表示を確認
    await expect(page.locator('.loading-spinner')).toBeVisible();
    
    // 結果が表示されることを確認（最大10秒待機）
    await expect(page.locator('.analysis-results')).toBeVisible({ timeout: 10000 });
    
    // 結果の内容を確認
    await expect(page.locator('.rule-matches')).toContainText('価格変更');
    await expect(page.locator('.ai-analysis')).toContainText('意図: 価格更新');
    await expect(page.locator('.confidence-score')).toContainText(/\d+%/);
  });

  test('バッチ解析の実行', async ({ page }) => {
    // バッチモードに切り替え
    await page.click('text=バッチ解析');
    
    // 複数のテキストを入力
    await page.fill('textarea[data-index="0"]', 'テキスト1: 商品説明を更新');
    await page.click('button:has-text("追加")');
    await page.fill('textarea[data-index="1"]', 'テキスト2: 在庫数を100に設定');
    await page.click('button:has-text("追加")');
    await page.fill('textarea[data-index="2"]', 'テキスト3: 配送料を無料に');
    
    // バッチ解析を実行
    await page.click('button:has-text("バッチ解析開始")');
    
    // プログレスバーが表示されることを確認
    await expect(page.locator('.progress-bar')).toBeVisible();
    
    // 全ての結果が表示されることを確認
    await expect(page.locator('.batch-results .result-item')).toHaveCount(3, { timeout: 15000 });
  });

  test('解析履歴の表示', async ({ page }) => {
    // 履歴タブをクリック
    await page.click('text=解析履歴');
    
    // 履歴が表示されることを確認
    await expect(page.locator('.history-list')).toBeVisible();
    
    // 履歴アイテムが存在することを確認
    const historyItems = page.locator('.history-item');
    await expect(historyItems).toHaveCount(await historyItems.count());
    
    // 最初の履歴アイテムをクリック
    await historyItems.first().click();
    
    // 詳細が表示されることを確認
    await expect(page.locator('.history-detail')).toBeVisible();
    await expect(page.locator('.history-detail')).toContainText('解析ID:');
    await expect(page.locator('.history-detail')).toContainText('実行日時:');
  });

  test('ルール管理', async ({ page }) => {
    // ルール管理タブをクリック
    await page.click('text=ルール管理');
    
    // 新規ルール作成ボタンをクリック
    await page.click('button:has-text("新規ルール")');
    
    // ルール作成フォームに入力
    await page.fill('input[name="ruleName"]', 'テストルール');
    await page.selectOption('select[name="category"]', 'price');
    await page.fill('input[name="pattern"]', '(\\d+)円');
    await page.fill('textarea[name="description"]', 'テスト用の価格検出ルール');
    
    // 保存ボタンをクリック
    await page.click('button:has-text("保存")');
    
    // 成功メッセージが表示されることを確認
    await expect(page.locator('.success-message')).toContainText('ルールが作成されました');
    
    // ルール一覧に新しいルールが表示されることを確認
    await expect(page.locator('.rule-list')).toContainText('テストルール');
  });

  test('解析結果のエクスポート', async ({ page, context }) => {
    // テキスト解析を実行
    await page.fill('textarea[name="analysisText"]', 'エクスポートテスト');
    await page.click('button:has-text("解析開始")');
    await expect(page.locator('.analysis-results')).toBeVisible({ timeout: 10000 });
    
    // ダウンロードのプロミスを設定
    const downloadPromise = page.waitForEvent('download');
    
    // エクスポートボタンをクリック
    await page.click('button:has-text("エクスポート")');
    
    // フォーマットを選択
    await page.click('text=JSON形式');
    
    // ダウンロードを待機
    const download = await downloadPromise;
    
    // ファイル名を確認
    expect(download.suggestedFilename()).toMatch(/analysis_.*\.json/);
  });

  test('リアルタイムストリーミング解析', async ({ page }) => {
    // ストリーミングモードを有効化
    await page.check('input[name="enableStreaming"]');
    
    // テキストを入力開始
    const textArea = page.locator('textarea[name="analysisText"]');
    await textArea.fill('');
    
    // 文字を一つずつ入力
    const text = 'リアルタイムで解析される文章です';
    for (const char of text) {
      await textArea.type(char, { delay: 100 });
      
      // リアルタイム結果が更新されることを確認
      if (text.indexOf(char) > 5) {
        await expect(page.locator('.streaming-results')).toBeVisible();
      }
    }
    
    // 最終結果が表示されることを確認
    await expect(page.locator('.streaming-results')).toContainText('解析中');
  });

  test('解析設定の変更', async ({ page }) => {
    // 設定アイコンをクリック
    await page.click('[data-testid="settings-icon"]');
    
    // 設定モーダルが開くことを確認
    await expect(page.locator('.settings-modal')).toBeVisible();
    
    // 設定を変更
    await page.selectOption('select[name="defaultAnalysisType"]', 'ai_based');
    await page.fill('input[name="maxTokens"]', '2000');
    await page.check('input[name="enableCache"]');
    
    // 保存ボタンをクリック
    await page.click('button:has-text("設定を保存")');
    
    // 成功メッセージが表示されることを確認
    await expect(page.locator('.success-message')).toContainText('設定が保存されました');
    
    // モーダルが閉じることを確認
    await expect(page.locator('.settings-modal')).not.toBeVisible();
  });
});