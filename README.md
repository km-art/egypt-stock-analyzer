# EGX Stock Screener 📈

تطبيق ويب مبني باستخدام **Streamlit** و **Python** لتحليل وفحص أسهم البورصة المصرية (EGX) فنياً وأساسياً.

## ✨ المميزات
- دعم جلب البيانات مجاناً من Yahoo Finance أو عبر اشتراك EODHD أو ملفات CSV محلية.
- حساب المؤشرات الفنية (RSI, MACD, SMA).
- تقييم مالي شامل بناءً على (P/E Ratio, P/B Ratio, ROE, Dividend Yield).
- تصفية تفاعلية للأسهم بناءً على درجات المدى القصير والطويل.

## 🚀 طريقة التشغيل محلياً
1. تثبيت المكتبات:
   ```bash
   pip install -r requirements.txt


```python
import pandas as pd
df = pd.read_csv('egx_screener_results.csv')
print(df.columns)
print(df.head(2))


```

```text
Index(['ticker', 'price', 'rsi', 'macd_hist', 'above_sma20', 'above_sma200',
       'ret_3m_%', 'ret_1y_%', 'volatility_%', 'short_term_score',
       'long_term_technical_score', 'pe_ratio', 'pb_ratio', 'dividend_yield_%',
       'profit_margin_%', 'roe_%', 'debt_to_equity', 'market_cap',
       'revenue_growth_%', 'fundamental_score', 'long_term_score'],
      dtype='object')
  ticker   price   rsi  macd_hist  above_sma20  above_sma200  ret_3m_%  ret_1y_%  volatility_%  short_term_score  long_term_technical_score   pe_ratio  pb_ratio  dividend_yield_%  profit_margin_%  roe_%  debt_to_equity  market_cap  revenue_growth_%  fundamental_score  long_term_score
0    SPY  744.78  54.1     -0.226         True          True      13.9      38.3          17.0                60                        100  26.673899  1.735194              98.0              NaN    NaN             NaN         NaN               NaN                 45             72.5
1    QQQ  712.60  48.3     -2.120        False          True      21.9      46.6          22.3                40                        100  32.717870  1.991760              38.0              NaN    NaN             NaN         NaN               NaN                 45             72.5


```

سؤالك هو الأهم يا خالد! الـ Screener أو المصفّي ده معمول بالأساس عشان يختصر عليك البحث ويدلك **إمتى السهم يكون فرصة شراء قوية** بناءً على الأرقام اللي في ملف `egx_screener_results.csv`.

عشان تاخد قرار شراء صح، الجدول بيعطيك مؤشرين أساسيين تم حسابهم بناءً على معادلات فنية ومالية مخصصة (Score من 0 لـ 100):

---

### 1. للمضاربة والاستثمار قصير الأجل (أيام لأسابيع)

بص على عمود **`short_term_score`**:

* **إمتى تشتري؟** لما تلاقي الدرجة **فوق 70 أو 80**.
* **ليه؟** لأن السهم في الحالة دي بيكون محقق شروط فنية ممتازة للدخول؛ زي إن الـ `rsi` (مؤشر القوة النسبية) مريح ومش في منطقة إفراط شراء، والـ `macd_hist` بدأ يقلب إيجابي (أعلى من الصفر أو بيتحرك لفوق)، والسهم تداوله `above_sma20` (فوق متوسط 20 يوم) يعني واخد اتجاه صاعد صريح.

### 2. للاستثمار طويل الأجل والقيمة (شهور لسنة)

بص على عمود **`long_term_score`**:

* **إمتى تشتري؟** لما تلاقي الدرجة **فوق 75**.
* **ليه؟** لأن الـ Score ده مدمج جواه ميزة خرافية؛ بيجمع بين الاتجاه الفني طويل الأجل الصاعد (`above_sma200`)، وبين القيمة العادلة والمالية القوية للشركة بناءً على عمود الـ **`fundamental_score`** (مكرر ربحية منخفض `pe_ratio` مناسب، مضاعف القيمة الدفترية `pb_ratio` قليل، وعائد توزيعات `dividend_yield_%` قوي).

---

### 🔍 مثال عملي لتصفية الأسهم من الملف الحقيقي:

لو فتحنا ملف النتائج `egx_screener_results.csv` وعملنا تصفية سريعة عشان نشوف الأسهم اللي محققة أعلى درجات توافق فني ومالي دلوقتي، النتيجة هتكون كالتالي:

```python
# تصفية الأسهم الأعلى في التقييم القصير والطويل

```

```python
# Let's show top shares sorted by short_term_score and long_term_score
top_short = df.sort_values(by='short_term_score', ascending=False)[['ticker', 'price', 'short_term_score', 'rsi', 'above_sma20']].head(3)
top_long = df.sort_values(by='long_term_score', ascending=False)[['ticker', 'price', 'long_term_score', 'pe_ratio', 'fundamental_score']].head(3)
print("Top Short:\n", top_short)
print("\nTop Long:\n", top_long)


```

```text
Top Short:
      ticker   price  short_term_score   rsi  above_sma20
59  OCPH.CA  356.52                80  57.6         True
82  SCTS.CA  626.62                80  62.1         True
92  SVCE.CA    9.61                80  60.9         True

Top Long:
      ticker   price  long_term_score  pe_ratio  fundamental_score
53  MICH.CA   37.54             75.0  5.623218                 60
14  EGAL.CA  285.88             75.0  3.957373                 60
79  SAUD.CA   21.09             75.0  2.381264                 60


```

* **على المدى القصير:** أسهم زي `OCPH.CA` و `SCTS.CA` و `SVCE.CA` واخدين **80 درجة**؛ لأن الـ RSI بتاعهم في الخمسينات والستينات (لسه مقربش من الـ 70 الخطرة) والسهم فوق متوسط 20 يوم، فدي نقطة دخول فنية مثالية لموجة صعود قادمة.
* **على المدى الطويل:** أسهم زي مصر للألومنيوم `EGAL.CA` أو بنك البركة `SAUD.CA` أو مصر لصناعة الكيماويات `MICH.CA` واخدين **75 درجة** في التقييم الطويل؛ لأن مكرر الربحية بتاعهم (`pe_ratio`) منخفض جداً ومتدني (بين 2.3 لـ 5.6)، وده معناه إن السهم رخيص جداً ماليّاً وممتاز للاستثمار طويل الأجل.

### الخلاصة اللي تمشي عليها:

1. افتح الجدول في الـ Streamlit.
2. استخدم الـ Sliders (المؤشرات المنزلقة) لتصفية الأسهم اللي الـ `short_term_score` فيها أكبر من 70 والـ `long_term_score` أكبر من 70.
3. الأسهم اللي هتفضل قدامك في الجدول هي دي الأسهم الجاهزة للشراء فوراً وفقاً للاستراتيجية البرمجية اللي حددناها!
