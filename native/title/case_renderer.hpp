// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "gfx/draw_list.hpp"
#include "ui/fonts.hpp"
namespace hui::demo {struct Item;}
void niak_draw_rotating_case(hui::gfx::DrawList &list,const hui::demo::Item &game,
                            const hui::gfx::Rect &bounds,float seconds,
                            const hui::ui::Fonts &fonts);
