import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";

import { CategoryPickerScreen } from "../screens/CategoryPickerScreen";
import { DuelHistoryScreen } from "../screens/DuelHistoryScreen";
import { DuelScreen } from "../screens/DuelScreen";
import { DuelsListScreen } from "../screens/DuelsListScreen";
import { PlayQuestionScreen } from "../screens/PlayQuestionScreen";

export type RootStackParamList = {
  DuelsList: undefined;
  Duel: { duelId: number };
  CategoryPicker: { duelId: number; roundSequence: number };
  PlayQuestion: { duelId: number; roundId: number; position: number };
  DuelHistory: { duelId: number };
};

const Stack = createNativeStackNavigator<RootStackParamList>();

export function RootNavigator() {
  return (
    <NavigationContainer>
      <Stack.Navigator>
        <Stack.Screen name="DuelsList" component={DuelsListScreen} options={{ title: "Christduell" }} />
        <Stack.Screen name="Duel" component={DuelScreen} options={{ title: "Duell" }} />
        <Stack.Screen
          name="CategoryPicker"
          component={CategoryPickerScreen}
          options={{ title: "Kategorie wählen" }}
        />
        <Stack.Screen
          name="PlayQuestion"
          component={PlayQuestionScreen}
          options={{ title: "Frage" }}
        />
        <Stack.Screen
          name="DuelHistory"
          component={DuelHistoryScreen}
          options={{ title: "Verlauf" }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
