MISSION 5 - W5 PATCH (cutscenes)
Overlay into the project root (after W1, W2, W3, W4). Root-relative paths.

NEW
  src/cutscenes/m5martial.py  eight bespoke 2D scenes in the m4aftermath
                              idiom (composition inside SAFE_TOP..SAFE_BOT;
                              helpers imported from m3ko/m3cell/chair/route12;
                              every named figure via cutscenes.cast):
                                intro   m5_tv_bulletin      state studio read,
                                        chyron "BALACEANU DEATH 'SUICIDE'",
                                        echo monitor top-right
                                        m5_safehouse_tv     Biribel at the rainy
                                        window, back to a CRT playing the bulletin
                                        m5_retardovici_tv   podium / presidential
                                        seal / twin flags / empty crowd address
                                ending  m5_river_gate       Maru through the iron
                                        gate, red scope dot arriving on Biribel
                                        m5_ucilev_scope     optic reticle + mil-dots
                                        + RANGE/WIND HUD, breath sway settling
                                        m5_ucilev_reveal    Guard black + red
                                        armband, rifle lowering ("Not tonight")
                                        m5_ucilev_leaves    walks off into the rain
                                        toward the gate lamp
                                        m5_radio            split-frame quay <->
                                        Vasile's office with the new flag
CHANGED
  src/cutscenes/engine.py     imports the eight _draw_m5_* fns and dispatches
                              their scene names in draw_cutscene_scene (after
                              m4_roof_dawn); title cards stay engine-drawn
  tools/smoke_test.py         check_mission5_cutscene_shots upgraded from the W4
                              lit-backdrop tolerance to the M4 tonal-spread bar
                              (std-dev > 3.0 at t=0/1500/4000/9000 per non-title
                              shot) + the scene-name set assertion
  docs/MISSION5_BUILD_PLAN.md W5 ticked
  docs/worklog.md             W5 entry
  RESUME_PROMPT.txt           points at W6
NEW (docs)
  MISSION5_W5_README.txt      this file
NOTE  font_glyph_coverage caught that the radio tag used U+2194 (↔), which
      oswald has no glyph for (tofu). Switched to ASCII "<->". Keep all rendered
      cutscene text inside the covered glyph set.
Gate: compileall OK, SMOKE TEST: OK (incl. mission5_cutscene_shots spread
assertion + font_glyph_coverage). Verified live: --dev-mission5 plays the
bulletin chain through the real app loop (shots/m5_w5/intro_f*.png).
