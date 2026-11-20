# tr2en v0.2.1 (Beta)

Yerel (çevrimdışı) model için düzeltme sürümü.

## Düzeltmeler

- **Numaralı ve madde işaretli listeler bozulmuyor.** Birden çok satırlık bir liste seçilip yerel modelle çevrildiğinde numaralar cümleye karışıyordu ("2. Toplantı…" → "The 2nd meeting…"). Satır başındaki `1.`, `2)`, `-`, `•` işaretleri artık olduğu gibi korunuyor; tek satırlık "3. maddeye göre…" gibi sıra sayıları da doğru çevriliyor.
- **Anlamı tersine dönen çeviri yapıştırılmıyor.** "Yapamayacaklarımızdan değil, yapabileceklerimizden bahsedelim." gibi "…-me değil, …" kalıbındaki cümlelerde yerel model anlamı ters çevirebiliyordu ve bu çeviri güvenlik kontrolünden geçiyordu. Artık yapıştırılmıyor: Bulut seçiliyse çeviri buluttan yapılır, yalnızca yerel model kullanılıyorsa "Olumsuzluk şüphesi — çevrilmedi" uyarısı çıkar. Olumsuzluk kontrolü yerel modelde artık cümle cümle yapılıyor; uzun bir seçimde başka bir cümledeki "not" kaybolan olumsuzluğu gizlemiyor.
- **"Kusura bakmayın" artık çevriliyor.** Özür kalıbı yanlışlıkla olumsuz cümle sayılıyor ve çeviri engelleniyordu.

## Yükseltme

Kurulum dosyasını çalıştırmak yeterli: açık tr2en kendini kapatır, ayarlarınız ve model korunur.

---

# tr2en v0.2.1 (Beta)

A bug-fix release for the local (offline) model.

## Fixes

- **Numbered and bulleted lists stay intact.** When a multi-line list was translated with the local model, the numbers leaked into the sentences ("2. Toplantı…" → "The 2nd meeting…"). Leading `1.`, `2)`, `-`, `•` markers are now kept as they are; single-line ordinals such as "3. maddeye göre…" are still translated correctly.
- **Translations that flip the meaning are no longer pasted.** For "not X but Y" sentences in Turkish ("…-me değil, …"), the local model could reverse the meaning and the result passed the safety check. Such a translation is now refused: with Cloud selected it is translated by the cloud service, with the local model only you get a "negation suspected — not translated" notice. The local model's negation check now runs sentence by sentence, so a "not" in another sentence of a long selection no longer hides a lost negation.
- **"Kusura bakmayın" (sorry) is translated again.** This apology phrase was mistaken for a negative sentence and the translation was blocked.

## Upgrade

Just run the installer: a running tr2en closes itself, and your settings and model are kept.
