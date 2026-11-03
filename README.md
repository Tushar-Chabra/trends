# GitHub Trends in Hinglish

Roz ke top 10 trending GitHub projects, simple Hinglish mein, non-tech logon ke liye.
Kya karte hain, kitne safe hain, aur kiske kaam ke hain.

**Live page:** https://tushar-chabra.github.io/trends-in-hinglish/

## Ye page kya dikhata hai
- Aaj ke Top 3, stats, aur Daily / Weekly / Monthly / Yearly top 10
- Har project ke liye: kya karta hai, kyun bana, kyun zaroorat padi, kis kaam aayega
- Language chart, stars ka comparison, risk label (Low / Medium / High risk) aur warning
- "Risk guide" section: har label 5 fixed sawaalon se decide hota hai, simple example ke saath

## Data kahan se aata hai
Trendshift.io aur har project ka public GitHub page. Page roz ek baar update hota hai; link hamesha wahi rehta hai.

## Safety aur disclaimer (zaroor padhein)
- Ye sirf information hai, advice nahi. Risk label andaza hai, security audit nahi.
- Kuch bhi install karne se pehle uska official page khud padhein.
- Unknown website se command copy karke na chalayein. Software sirf official GitHub page se download karein.
- Apna password ya API key kisi ko na dein.
- Kisi bhi project ko install ya use karna aapka apna decision hai. Isse hone wale kisi bhi nuksaan ki responsibility is page ya iske owner ki nahi hai.
- Page kisi company ya project se linked nahi hai. Koi tracking ya cookies nahi.

## Privacy / technical notes
- Page ek single file (`index.html`) hai; isme koi tracking, analytics, cookies ya third-party script nahi.
- Sirf fonts Google Fonts se load hote hain, isliye font load hote time aapka IP address Google tak jata hai.
- Sab data page ke andar ek JSON block mein hai (code ki tarah chalta nahi). Dikhane se pehle har field check aur escape hoti hai.
- Content-Security-Policy sirf page ki apni ek script ko chalne deti hai; bahar ka koi script, network call ya form allowed nahi.
- Galti mili to GitHub Issues mein batayein.
