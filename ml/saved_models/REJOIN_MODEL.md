# Rejoining the split model file

`bilstm_sentiment.keras` is 32 MB, which is over the file-transfer limit, so it
arrived as two parts. Rejoin them once and you can delete the parts.

**In Command Prompt / Anaconda Prompt** (not PowerShell — `copy /b` is a cmd
builtin):

```
d:
cd D:\DineSense\ml\saved_models
copy /b bilstm_sentiment.keras.part00 + bilstm_sentiment.keras.part01 bilstm_sentiment.keras
```

**Or in PowerShell:**

```powershell
cd D:\DineSense\ml\saved_models
$out = [System.IO.File]::Create("bilstm_sentiment.keras")
foreach ($p in "bilstm_sentiment.keras.part00","bilstm_sentiment.keras.part01") {
    $bytes = [System.IO.File]::ReadAllBytes((Resolve-Path $p))
    $out.Write($bytes, 0, $bytes.Length)
}
$out.Close()
```

## Check it worked

The rejoined file must be exactly **32,374,850 bytes** with MD5
`4084382820208844a41267416be0a2aa`.

```powershell
(Get-Item bilstm_sentiment.keras).Length
Get-FileHash bilstm_sentiment.keras -Algorithm MD5
```

Then confirm it actually loads:

```
cd D:\DineSense
python ml\predict.py "the food was excellent but the service was slow"
```

If you see a sentiment and a list of aspects, it worked. Delete the `.part00`
and `.part01` files.

## If it fails

You do not strictly need this file. `predict.py` falls back to
`baseline_tfidf_logreg.joblib` automatically — and the baseline actually scored
*higher* (0.772 vs 0.748 macro F1). Retraining from scratch is also an option:
`python ml/train_bilstm.py --epochs 6`, about 10 minutes, fully reproducible
(fixed seed).
